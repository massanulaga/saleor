import graphene

from ......account.models import User, WishlistItem
from .....tests.utils import assert_no_permission, get_graphql_content

WISHLIST_ITEM_REMOVE_MUTATION = """
mutation($variantId: ID!) {
  wishlistItemRemove(variantId: $variantId) {
    accountErrors {
      field
      code
    }
  }
}
"""


def _variant_id(variant):
    return graphene.Node.to_global_id("ProductVariant", variant.pk)


def test_wishlist_item_remove_deletes_only_current_customer_item(
    user_api_client, customer_user, variant
):
    # given
    other_customer = User.objects.create(email="other-remove@example.com")
    WishlistItem.objects.create(customer=customer_user, variant=variant)
    WishlistItem.objects.create(customer=other_customer, variant=variant)
    variables = {"variantId": _variant_id(variant)}

    # when
    response = user_api_client.post_graphql(WISHLIST_ITEM_REMOVE_MUTATION, variables)

    # then
    data = get_graphql_content(response)["data"]["wishlistItemRemove"]
    assert not data["accountErrors"]
    assert not WishlistItem.objects.filter(customer=customer_user).exists()
    assert WishlistItem.objects.filter(
        customer=other_customer, variant=variant
    ).exists()


def test_wishlist_item_remove_variant_not_on_list_returns_not_found(
    user_api_client, variant
):
    # given
    variables = {"variantId": _variant_id(variant)}

    # when
    response = user_api_client.post_graphql(WISHLIST_ITEM_REMOVE_MUTATION, variables)

    # then
    data = get_graphql_content(response)["data"]["wishlistItemRemove"]
    assert data["accountErrors"][0]["field"] == "variantId"
    assert data["accountErrors"][0]["code"] == "NOT_FOUND"


def test_wishlist_item_remove_cannot_delete_other_customers_item(
    user_api_client, variant
):
    # given
    other_customer = User.objects.create(email="other-remove-only@example.com")
    WishlistItem.objects.create(customer=other_customer, variant=variant)
    variables = {"variantId": _variant_id(variant)}

    # when
    response = user_api_client.post_graphql(WISHLIST_ITEM_REMOVE_MUTATION, variables)

    # then
    data = get_graphql_content(response)["data"]["wishlistItemRemove"]
    assert data["accountErrors"][0]["code"] == "NOT_FOUND"
    assert WishlistItem.objects.filter(
        customer=other_customer, variant=variant
    ).exists()


def test_wishlist_item_remove_anonymous_client_is_rejected(
    api_client, customer_user, variant
):
    # given
    WishlistItem.objects.create(customer=customer_user, variant=variant)
    variables = {"variantId": _variant_id(variant)}

    # when
    response = api_client.post_graphql(WISHLIST_ITEM_REMOVE_MUTATION, variables)

    # then
    assert_no_permission(response)
    assert WishlistItem.objects.filter(customer=customer_user, variant=variant).exists()
