import pytest
from django.db import IntegrityError, transaction

from ...product.models import ProductVariant
from ..models import User, WishlistItem


def test_wishlist_item_is_unique_per_customer_and_variant(customer_user, variant):
    WishlistItem.objects.create(customer=customer_user, variant=variant)

    with pytest.raises(IntegrityError), transaction.atomic():
        WishlistItem.objects.create(customer=customer_user, variant=variant)


def test_wishlist_items_are_isolated_per_customer(
    customer_user, customer_user2, variant
):
    WishlistItem.objects.create(customer=customer_user, variant=variant)
    WishlistItem.objects.create(customer=customer_user2, variant=variant)

    assert list(
        WishlistItem.objects.filter(customer=customer_user).values_list(
            "variant_id", flat=True
        )
    ) == [variant.pk]
    assert WishlistItem.objects.filter(customer=customer_user).count() == 1
    assert WishlistItem.objects.filter(customer=customer_user2).count() == 1


def test_wishlist_items_are_ordered_by_creation(customer_user, variant, product):
    other_variant = ProductVariant.objects.create(
        product=product, sku="wishlist-second", name="Second"
    )
    first = WishlistItem.objects.create(customer=customer_user, variant=variant)
    second = WishlistItem.objects.create(customer=customer_user, variant=other_variant)

    assert list(WishlistItem.objects.filter(customer=customer_user)) == [first, second]


def test_wishlist_items_are_removed_when_customer_is_deleted(customer_user, variant):
    WishlistItem.objects.create(customer=customer_user, variant=variant)

    User.objects.filter(pk=customer_user.pk).delete()

    assert not WishlistItem.objects.exists()


def test_wishlist_items_are_removed_when_variant_is_deleted(customer_user, variant):
    WishlistItem.objects.create(customer=customer_user, variant=variant)

    ProductVariant.objects.filter(pk=variant.pk).delete()

    assert not WishlistItem.objects.exists()
