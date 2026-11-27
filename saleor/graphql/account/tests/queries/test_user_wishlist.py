from datetime import timedelta

import graphene
from django.utils import timezone

from .....account.models import User, WishlistItem
from .....product.models import ProductChannelListing
from ....tests.utils import assert_no_permission, get_graphql_content

QUERY_USER_WISHLIST = """
query userWishlist($customerId: ID!) {
    user(id: $customerId) {
        id
        wishlist {
            id
            createdAt
            variant {
                id
            }
            product {
                id
                name
            }
        }
    }
}
"""

QUERY_ME_WISHLIST = """
query meWishlist {
    me {
        id
        wishlist {
            id
        }
    }
}
"""

QUERY_CUSTOMERS_WISHLIST = """
query customersWishlist {
    customers(first: 10) {
        edges {
            node {
                email
                wishlist {
                    variant {
                        id
                    }
                }
            }
        }
    }
}
"""

REMOVE_WISHLIST_ITEM_MUTATION = """
mutation wishlistItemRemove($variantId: ID!) {
    wishlistItemRemove(variantId: $variantId) {
        errors {
            field
            code
        }
    }
}
"""


def test_user_wishlist_returns_customer_items_for_staff(
    staff_api_client,
    permission_manage_users,
    customer_user,
    product_with_two_variants,
):
    # given
    now = timezone.now()
    first_variant, second_variant = product_with_two_variants.variants.all()[:2]
    newer = WishlistItem.objects.create(customer=customer_user, variant=second_variant)
    older = WishlistItem.objects.create(customer=customer_user, variant=first_variant)
    WishlistItem.objects.filter(pk=older.pk).update(created_at=now - timedelta(days=1))
    WishlistItem.objects.filter(pk=newer.pk).update(created_at=now)
    customer_id = graphene.Node.to_global_id("User", customer_user.pk)

    # when
    response = staff_api_client.post_graphql(
        QUERY_USER_WISHLIST,
        variables={"customerId": customer_id},
        permissions=[permission_manage_users],
    )

    # then
    content = get_graphql_content(response)["data"]["user"]
    assert content["id"] == customer_id
    assert [item["variant"]["id"] for item in content["wishlist"]] == [
        graphene.Node.to_global_id("ProductVariant", first_variant.pk),
        graphene.Node.to_global_id("ProductVariant", second_variant.pk),
    ]
    assert content["wishlist"][0]["product"]["name"] == first_variant.product.name


def test_user_wishlist_denied_without_permission(
    staff_api_client, customer_user, variant
):
    # given
    WishlistItem.objects.create(customer=customer_user, variant=variant)
    customer_id = graphene.Node.to_global_id("User", customer_user.pk)

    # when
    response = staff_api_client.post_graphql(
        QUERY_USER_WISHLIST, variables={"customerId": customer_id}
    )

    # then
    assert_no_permission(response)


def test_user_wishlist_denied_for_the_customer_themselves(
    user_api_client, customer_user, variant
):
    # given
    WishlistItem.objects.create(customer=customer_user, variant=variant)

    # when
    response = user_api_client.post_graphql(QUERY_ME_WISHLIST)

    # then
    assert_no_permission(response)


def test_user_wishlist_hides_unpublished_variants(
    staff_api_client, permission_manage_users, customer_user, variant
):
    # given
    WishlistItem.objects.create(customer=customer_user, variant=variant)
    ProductChannelListing.objects.filter(product=variant.product).update(
        is_published=False
    )
    customer_id = graphene.Node.to_global_id("User", customer_user.pk)

    # when
    response = staff_api_client.post_graphql(
        QUERY_USER_WISHLIST,
        variables={"customerId": customer_id},
        permissions=[permission_manage_users],
    )

    # then
    content = get_graphql_content(response)["data"]["user"]
    assert content["wishlist"] == []


def test_user_wishlist_returns_each_customers_own_items(
    staff_api_client,
    permission_manage_users,
    customer_user,
    variant,
    product_with_two_variants,
):
    # given
    other_customer = User.objects.create(email="other-wishlist@example.com")
    no_items_customer = User.objects.create(email="empty-wishlist@example.com")
    other_variant = product_with_two_variants.variants.first()
    WishlistItem.objects.create(customer=customer_user, variant=variant)
    WishlistItem.objects.create(customer=other_customer, variant=other_variant)

    # when
    response = staff_api_client.post_graphql(
        QUERY_CUSTOMERS_WISHLIST, permissions=[permission_manage_users]
    )

    # then
    edges = get_graphql_content(response)["data"]["customers"]["edges"]
    wishlists = {
        edge["node"]["email"]: [
            item["variant"]["id"] for item in edge["node"]["wishlist"]
        ]
        for edge in edges
    }
    assert wishlists[customer_user.email] == [
        graphene.Node.to_global_id("ProductVariant", variant.pk)
    ]
    assert wishlists[other_customer.email] == [
        graphene.Node.to_global_id("ProductVariant", other_variant.pk)
    ]
    assert wishlists[no_items_customer.email] == []


def test_staff_wishlist_remove_does_not_touch_customer_list(
    staff_api_client, permission_manage_users, customer_user, variant
):
    # given
    customer_item = WishlistItem.objects.create(customer=customer_user, variant=variant)
    variant_id = graphene.Node.to_global_id("ProductVariant", variant.pk)

    # when
    response = staff_api_client.post_graphql(
        REMOVE_WISHLIST_ITEM_MUTATION,
        variables={"variantId": variant_id},
        permissions=[permission_manage_users],
        check_no_permissions=False,
    )

    # then
    content = get_graphql_content(response)["data"]["wishlistItemRemove"]
    assert content["errors"]
    assert WishlistItem.objects.filter(pk=customer_item.pk).exists()
