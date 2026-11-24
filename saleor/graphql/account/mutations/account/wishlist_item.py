from typing import cast

import graphene
from django.core.exceptions import ValidationError

from .....account import models
from .....account.error_codes import AccountErrorCode
from .....permission.auth_filters import AuthorizationFilters
from ....core import ResolveInfo
from ....core.doc_category import DOC_CATEGORY_USERS
from ....core.mutations import BaseMutation
from ....core.types import AccountError
from ....product.types import ProductVariant
from ...resolvers import get_wishlist_visible_variants
from ...types import WishlistItem


class WishlistItemAdd(BaseMutation):
    wishlist_item = graphene.Field(
        WishlistItem, description="The wishlist item for the saved variant."
    )

    class Arguments:
        variant_id = graphene.ID(
            required=True, description="ID of the product variant to save."
        )

    class Meta:
        description = (
            "Saves a product variant to the wishlist of the authenticated customer. "
            "Saving a variant that is already on the wishlist returns the existing item."
        )
        doc_category = DOC_CATEGORY_USERS
        error_type_class = AccountError
        error_type_field = "account_errors"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(  # type: ignore[override]
        cls, _root, info: ResolveInfo, /, *, variant_id
    ):
        user = cast(models.User, info.context.user)
        variant = cls.get_node_or_error(
            info,
            variant_id,
            field="variant_id",
            only_type=ProductVariant,
            qs=get_wishlist_visible_variants(),
        )
        wishlist_item, _ = models.WishlistItem.objects.get_or_create(
            customer=user, variant=variant
        )
        return cls(wishlist_item=wishlist_item)


class WishlistItemRemove(BaseMutation):
    class Arguments:
        variant_id = graphene.ID(
            required=True, description="ID of the product variant to remove."
        )

    class Meta:
        description = (
            "Removes a product variant from the wishlist of the authenticated customer."
        )
        doc_category = DOC_CATEGORY_USERS
        error_type_class = AccountError
        error_type_field = "account_errors"
        permissions = (AuthorizationFilters.AUTHENTICATED_USER,)

    @classmethod
    def perform_mutation(  # type: ignore[override]
        cls, _root, info: ResolveInfo, /, *, variant_id
    ):
        user = cast(models.User, info.context.user)
        variant = cls.get_node_or_error(
            info, variant_id, field="variant_id", only_type=ProductVariant
        )
        deleted_count, _ = models.WishlistItem.objects.filter(
            customer=user, variant=variant
        ).delete()
        if not deleted_count:
            raise ValidationError(
                {
                    "variant_id": ValidationError(
                        "The product variant is not in the wishlist.",
                        code=AccountErrorCode.NOT_FOUND.value,
                    )
                }
            )
        return cls()
