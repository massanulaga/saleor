from datetime import timedelta

import graphene
from django.utils import timezone

from .....account.models import User, WishlistItem
from .....product.models import ProductChannelListing
from ....tests.utils import assert_no_permission, get_graphql_content

WISHLIST_QUERY = """
    query Wishlist {
        wishlist {
            id
            createdAt
            variant {
                id
                name
            }
            product {
                id
                name
            }
        }
    }
"""


def test_wishlist_returns_only_requesting_customer_items(
    user_api_client, customer_user, variant, product_with_two_variants
):
    # given
    other_customer = User.objects.create(email="other-wishlist@example.com")
    other_variant = product_with_two_variants.variants.first()
    WishlistItem.objects.create(customer=customer_user, variant=variant)
    WishlistItem.objects.create(customer=other_customer, variant=other_variant)

    # when
    response = user_api_client.post_graphql(WISHLIST_QUERY)

    # then
    content = get_graphql_content(response)
    items = content["data"]["wishlist"]
    assert len(items) == 1
    assert items[0]["variant"]["id"] == graphene.Node.to_global_id(
        "ProductVariant", variant.pk
    )
    assert items[0]["product"]["name"] == variant.product.name


def test_wishlist_is_ordered_by_saved_date(
    user_api_client, customer_user, variant, product_with_two_variants
):
    # given
    now = timezone.now()
    first_variant, second_variant = product_with_two_variants.variants.all()[:2]
    newer = WishlistItem.objects.create(customer=customer_user, variant=second_variant)
    older = WishlistItem.objects.create(customer=customer_user, variant=first_variant)
    WishlistItem.objects.filter(pk=older.pk).update(created_at=now - timedelta(days=1))
    WishlistItem.objects.filter(pk=newer.pk).update(created_at=now)

    # when
    response = user_api_client.post_graphql(WISHLIST_QUERY)

    # then
    items = get_graphql_content(response)["data"]["wishlist"]
    assert [item["variant"]["id"] for item in items] == [
        graphene.Node.to_global_id("ProductVariant", first_variant.pk),
        graphene.Node.to_global_id("ProductVariant", second_variant.pk),
    ]


def test_wishlist_anonymous_client_is_rejected(api_client, variant, customer_user):
    # given
    WishlistItem.objects.create(customer=customer_user, variant=variant)

    # when
    response = api_client.post_graphql(WISHLIST_QUERY)

    # then
    assert_no_permission(response)


def test_wishlist_hides_variant_unpublished_after_saving(
    user_api_client, customer_user, variant
):
    # given
    WishlistItem.objects.create(customer=customer_user, variant=variant)
    ProductChannelListing.objects.filter(product=variant.product).update(
        is_published=False
    )

    # when
    response = user_api_client.post_graphql(WISHLIST_QUERY)

    # then
    assert get_graphql_content(response)["data"]["wishlist"] == []
