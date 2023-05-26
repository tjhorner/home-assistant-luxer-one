import aiohttp
import uuid


class LuxerOneAuthorizationError(Exception):
    pass


class LuxerOneClient:
    def __init__(
        self, username: str, password: str, session: aiohttp.ClientSession | None = None
    ) -> None:
        self.base_url = "https://resident-api.luxerone.com/resident_api/v1"
        self.username = username
        self.password = password
        self.token = None

        if session is None:
            self.session = aiohttp.ClientSession()
        else:
            self.session = session

    async def get_auth_headers(self):
        if not self.token:
            return {}
        return {"Authorization": f"LuxerOneApi {self.token}"}

    async def check_response(self, response):
        json_data = await response.json()
        if json_data.get("error") == "ApiAuthorizationRequired":
            await self.login()
            return True
        return False

    async def request(
        self, method, endpoint, data=None, params=None, is_retry=False
    ) -> dict:
        url = self.base_url + endpoint
        headers = await self.get_auth_headers()

        async with self.session.request(
            method, url, data=data, params=params, headers=headers
        ) as response:
            reauthorized = await self.check_response(response)
            if reauthorized and not is_retry:
                return await self.request(
                    method, endpoint, data=data, params=params, is_retry=True
                )
            elif reauthorized and is_retry:
                raise LuxerOneAuthorizationError(
                    "Reauthorization failed when calling Luxer One API - credentials may be invalid."
                )
            else:
                return await response.json()

    async def get(self, endpoint, params=None):
        return await self.request("GET", endpoint, params=params)

    async def post(self, endpoint, data=None):
        return await self.request("POST", endpoint, data=data)

    async def login(self):
        req_id = hex(uuid.uuid4().int & (1 << 64) - 1)[2:]

        login_response = await self.post(
            "/auth/login",
            {
                "username": self.username,
                "password": self.password,
                "uuid": req_id,
                "as": "token",
                "expires": 1800,
                "remember": True,
            },
        )

        short_token = login_response["data"]["token"]
        self.token = short_token

        token_response = await self.post(
            "/auth/longterm", {"as": "token", "expire": 18000000}
        )

        self.token = token_response["data"]["token"]

    async def user_info(self):
        return await self.get("/user/info")

    async def pending_packages(self):
        return await self.get("/deliveries/pendings")

    async def package_history(self):
        return await self.get("/deliveries/history")
