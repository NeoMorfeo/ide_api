__VERSION__ = "0.0.3"

from datetime import datetime
import logging

from dateutil.tz import tzutc
import requests
from requests import Session

UTC = tzutc()

# logging.getLogger().setLevel(logging.DEBUG)

_LOGGER = logging.getLogger(__name__)


class IdeAPIError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


class UrlError(IdeAPIError):
    def __init__(self, status_code, message, request):
        self.status_code = status_code
        self.request = request
        super().__init__(message)

def serialize_date(dt):
    """
    Serialize a date/time value into an ISO8601 text representation
    adjusted (if needed) to UTC timezone.

    For instance:
    >>> serialize_date(datetime(2012, 4, 10, 22, 38, 20, 604391))
    '2012-04-10T22:38:20.604391Z'
    """
    if dt.tzinfo:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.isoformat()


class ResponseException(Exception):
    pass


class LoginException(Exception):
    pass


class SessionException(Exception):
    pass


class NoResponseException(Exception):
    pass


class SelectContractException(Exception):
    pass


class IdeAPI:
    __session = None
    __credentials = {}
    __domain = "https://www.i-de.es"
    __login_url = __domain + "/consumidores/rest/loginNew/login"
    __watthourmeter_url = (
        __domain + "/consumidores/rest/escenarioNew/obtenerMedicionOnline/24"
    )
    __icp_status_url = __domain + "/consumidores/rest/rearmeICP/consultarEstado"
    __contracts_url = __domain + "/consumidores/rest/cto/listaCtos/"
    __contract_detail_url = __domain + "/consumidores/rest/detalleCto/detalle/"
    __contract_selection_url = __domain + "/consumidores/rest/cto/seleccion/"
    __obtener_escenarios_url = (
        __domain + "/consumidores/rest/escenarioNew/obtenerEscenariosRest/"
    )
    __obtener_escenario_url = (
        __domain + "/consumidores/rest/escenarioNew/refrescarEscenario/"
    )
    __guardar_escenario_url = (
        __domain + "/consumidores/rest/escenarioNew/confirmarMedicionOnLine/{}/1/{}"
    )
    __borrar_escenario_url = (
        __domain + "/consumidores/rest/escenarioNew/borrarEscenario/"
    )
    __obtener_periodo_url = (
        __domain
        + "/consumidores/rest/consumoNew/obtenerDatosConsumoPeriodo/fechaInicio/{}00:00:00/fechaFinal/{}00:00:00/"
    )  # date format: 07-11-2020 - that's 7 Nov 2020
    __obtener_periodo_generacion_url = (
        __domain
        + "/consumidores/rest/consumoNew/obtenerDatosGeneracionPeriodo/fechaInicio/{}00:00:00/fechaFinal/{}00:00:00/"
    )  # date format: 07-11-2020 - that's 7 Nov 2020
    __headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36",
        "Origin": "https://www.i-de.es/",
        "accept": "application/json; charset=utf-8",
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
    }

    def __init__(self, username, password, debug_level=logging.INFO):
        """IdeAPI class __init__ method."""
        self.username = username
        self.password = password
        session = None
        self.__session = session

    def login(self):
        """Creates session with your credentials"""
        self.__session = Session()
        login_data = (
            '["{}","{}",null,"Linux -","PC","Chrome 77.0.3865.90","0","","s"]'.format(
                self.username, self.password
            )
        )

        # _LOGGER.debug("Login Data {}".format(login_data))

        response = self.__session.request(
            "POST", self.__login_url, data=login_data, headers=self.__headers
        )

        if response.status_code != 200:
            self.__session = None
            raise ResponseException(
                "Response error, code: {}".format(response.status_code)
            )
        json_response = response.json()
        if json_response["success"] != "true":
            self.__session = None
            raise LoginException("Login error, bad login")

    def __check_session(self):
        if not self.__session:
            raise SessionException(
                "Session required, use login() method to obtain a session"
            )

    def measurement(self):
        """Returns a measurement from the powermeter."""
        self.__check_session()
        response = self.__session.request(
            "GET", self.__watthourmeter_url, headers=self.__headers
        )
        if response.status_code != 200:
            raise ResponseException(
                "Response error, code: {}".format(response.status_code)
            )
        if not response.text:
            raise NoResponseException
        json_response = response.json()

        _LOGGER.debug("Measurement Data {}".format(json_response))

        return {
            "id": json_response["codSolicitudTGT"],
            "meter": json_response["valLecturaContador"],
            "consumption": json_response["valMagnitud"],
            "icp": json_response["valInterruptor"],
            "raw_response": json_response,
        }

    def watthourmeter(self):
        """Returns your current power consumption."""
        return self.measurement()["meter"]

    def icpstatus(self):
        """Returns the status of your ICP."""
        self.__check_session()
        response = self.__session.request(
            "POST", self.__icp_status_url, headers=self.__headers
        )
        if response.status_code != 200:
            raise ResponseException(
                "Response error, code: {}".format(response.status_code)
            )
        if not response.text:
            raise NoResponseException
        json_response = response.json()
        if json_response["icp"] == "trueConectado":
            return True
        else:
            return False

    def contracts(self):
        self.__check_session()
        response = self.__session.request(
            "GET", self.__contracts_url, headers=self.__headers
        )
        if response.status_code != 200:
            raise ResponseException(
                "Response error, code: {}".format(response.status_code)
            )
        if not response.text:
            raise NoResponseException
        json_response = response.json()
        if json_response["success"]:
            return json_response["contratos"]

    def contract(self):
        self.__check_session()
        response = self.__session.request(
            "GET", self.__contract_detail_url, headers=self.__headers
        )
        if response.status_code != 200:
            raise ResponseException(
                "Response error, code: {}".format(response.status_code)
            )
        if not response.text:
            raise NoResponseException
        return response.json()

    def contractselect(self, id):
        self.__check_session()
        response = self.__session.request(
            "GET", self.__contract_selection_url + id, headers=self.__headers
        )
        if response.status_code != 200:
            raise ResponseException(
                "Response error, code: {}".format(response.status_code)
            )
        if not response.text:
            raise NoResponseException
        json_response = response.json()
        if not json_response["success"]:
            raise SelectContractException

    def scene_list(self):
        self.__check_session()
        response = self.__session.request(
            "GET", self.__obtener_escenarios_url, headers=self.__headers
        )
        if response.status_code != 200:
            raise ResponseException(
                "Response error, code: {}".format(response.status_code)
            )
        if not response.text:
            raise NoResponseException
        json_response = response.json()
        return {
            "scene_names": json_response["y"]["smps"],
            "raw_response": json_response,
        }

    def scene_get(self, name):
        self.__check_session()
        get_data = '{{"nomEscenario":"{}"}}'.format(name)
        response = self.__session.request(
            "POST", self.__obtener_escenario_url, data=get_data, headers=self.__headers
        )
        if response.status_code != 200:
            raise ResponseException(
                "Response error, code: {}".format(response.status_code)
            )
        if not response.text:
            raise NoResponseException
        json_response = response.json()
        return {
            "name": json_response["nomEscenario"],
            "description": json_response["descripcion"],
            "consumption": json_response["numLcaInsta"],
            "raw_response": json_response,
        }

    def scene_save(self, consumption, measurement_id, description):
        self.__check_session()
        name = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        save_data = '{{"nomEscenario":"{}","descripcion":"{}"}}'.format(
            name, description
        )
        response = self.__session.request(
            "POST",
            self.__guardar_escenario_url.format(consumption, measurement_id),
            data=save_data,
            headers=self.__headers,
        )
        if response.status_code != 200:
            raise ResponseException(
                "Response error, code: {}".format(response.status_code)
            )
        if not response.text:
            raise NoResponseException
        json_response = response.json()
        return {"name": json_response["nomEscenario"], "raw_response": json_response}

    def scene_delete(self, name):
        self.__check_session()
        delete_data = '{{"nomEscenario":"{}"}}'.format(name)
        response = self.__session.request(
            "POST",
            self.__borrar_escenario_url,
            data=delete_data,
            headers=self.__headers,
        )
        if response.status_code != 200:
            raise ResponseException(
                "Response error, code: {}".format(response.status_code)
            )
        return True

    def _consumption_raw(self, start, end):
        self.__check_session()
        start_str = start.strftime("%d-%m-%Y")
        end_str = end.strftime("%d-%m-%Y")

        response = self.__session.request(
            "GET",
            self.__obtener_periodo_url.format(start_str, end_str),
            headers=self.__headers,
        )
        if response.status_code != 200:
            raise ResponseException(
                "Response error, code: {}".format(response.status_code)
            )
        if not response.text:
            raise NoResponseException
        return response.json()

    # Get consumption data from a time period
    #
    # start/end: datetime.date objects indicating the time period (both inclusive)
    # The supported time range seems to be (not documented) from Jan 1 in the previous year and a max
    # length of one year.
    #
    # Returns a list of consumptions starting a midnight on the start day until 23:00 on the last day.
    # Each value is the hourly consumption in Wh.
    def consumption(self, start, end):
        json = self._consumption_raw(start, end)
        values = []
        for x in json["y"]["data"][0]:
            if x is None:
                values.append(None)
            else:
                values.append(float(x["valor"]))
        return values

    def _production_raw(self, start, end):
        self.__check_session()
        start_str = start.strftime("%d-%m-%Y")
        end_str = end.strftime("%d-%m-%Y")

        response = self.__session.request(
            "GET",
            self.__obtener_periodo_generacion_url.format(start_str, end_str),
            headers=self.__headers,
        )
        if response.status_code != 200:
            raise ResponseException(
                "Response error, code: {}".format(response.status_code)
            )
        if not response.text:
            raise NoResponseException
        return response.json()

    # Get production data from a time period
    #
    # start/end: datetime.date objects indicating the time period (both inclusive)
    # The supported time range seems to be (not documented) from Jan 1 in the previous year and a max
    # length of one year.
    #
    # Returns a list of productions starting a midnight on the start day until 23:00 on the last day.
    # Each value is the hourly production in Wh.
    def production(self, start, end):
        json = self._production_raw(start, end)
        values = []
        for x in json["y"]["data"][0]:
            if x is None:
                values.append(None)
            else:
                values.append(float(x["valor"]))
        return values

    # Get total consumption in Wh (Watt-hour) over a time period
    #
    # start/end: datetime.date objects indicating the time period (both inclusive)
    def total_consumption(self, start, end):
        return float(self._consumption_raw(start, end)["acumulado"])
