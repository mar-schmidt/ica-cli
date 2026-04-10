"""API constants (from ha-ica-todo mobile gateway)."""

from typing import Final

DEFAULT_ARTICLE_GROUP_ID: Final = 12


class API:
    """ICA identity and query endpoints."""

    class AppRegistration:
        APP_REGISTRATION_ENDPOINT: Final = "register"
        CLIENT_ID: Final = "ica-app-dcr-registration"
        CLIENT_SECRET: Final = (
            "uxLHTBvZ-Z2fV-SbrHl1E-tz7vB3jQFrwAdSLlbVMMu1rxDdvJU0s8KGu9d1wLS4"
        )

    class URLs:
        BASE_URL: Final = "https://ims.icagruppen.se"
        OAUTH2_AUTHORIZE_ENDPOINT: Final = "oauth/v2/authorize"
        OAUTH2_TOKEN_ENDPOINT: Final = "oauth/v2/token"
        LOGIN_ENDPOINT: Final = "authn/authenticate/IcaCustomers"
        QUERY_BASE: Final = "https://apimgw-pub.ica.se"
        MY_BASEITEMS_ENDPOINT: Final = (
            "sverige/digx/mobile/shoppinglistservice/v1/baseitems"
        )
        SYNC_MY_BASEITEMS_ENDPOINT: Final = (
            "sverige/digx/mobile/shoppinglistservice/v1/baseitems"
        )
        ARTICLES_ENDPOINT: Final = (
            "sverige/digx/mobile/shoppinglistservice/v1/articles"
        )
        OFFERS_SEARCH_ENDPOINT: Final = (
            "sverige/digx/mobile/offerservice/v1/offers/search"
        )
        PRODUCT_BARCODE_LOOKUP_ENDPOINT: Final = (
            "sverige/digx/mobile/productservice/v1/product/{}"
        )


MY_LISTS_ENDPOINT: Final = (
    "sverige/digx/mobile/shoppinglistservice/v1/shoppinglists"
)
MY_LIST_ENDPOINT: Final = (
    "sverige/digx/mobile/shoppinglistservice/v1/shoppinglists/{}"
)
MY_LIST_SYNC_ENDPOINT: Final = (
    "sverige/digx/mobile/shoppinglistservice/v1/shoppinglists/{}/sync"
)
MY_LIST_CREATE_ENDPOINT: Final = "sverige/digx/shopping-list/v1/api/list/"
MY_STORES_ENDPOINT: Final = "sverige/digx/mobile/storeservice/v1/favorites"
STORE_ENDPOINT: Final = "sverige/digx/mobile/storeservice/v1/stores/{}"
STORE_OFFERS_ENDPOINT: Final = (
    "sverige/digx/mobile/offerservice/v1/offersdiscounts/{}"
)
ARTICLEGROUPS_ENDPOINT: Final = (
    "sverige/digx/mobile/shoppinglistservice/v1/articles/"
    "articlegroups?lastsyncdate={}"
)
RECIPE_ENDPOINT: Final = (
    "sverige/digx/mobile/recipeservice/v1/recipes/{}?api-version=2.0"
)
RANDOM_RECIPES_ENDPOINT: Final = (
    "sverige/digx/mobile/recipeservice/v1/recipes/random?numberofrecipes={}"
)
MY_RECIPES_FAVORITES_ENDPOINT: Final = (
    "sverige/digx/mobile/recipeservice/v1/favorites"
)

# Handla web (cookie auth) — see ica_cli.handla_cart
HANDLA_PRIVATKUND_HOST: Final = "https://handlaprivatkund.ica.se"
