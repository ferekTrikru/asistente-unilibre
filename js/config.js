/* =====================================================================
   Configuración del frontend (la cargan todas las pantallas).
   backendUrl: dónde corre el backend (FastAPI). En local es 127.0.0.1:8000
   (no "localhost": en Windows esa dirección intenta primero IPv6 y cada
   petición pierde ~2 s). Al desplegar, poner aquí la URL pública del backend;
   si se deja vacía, el chat funciona sin documentos (respuestas fijas + citas
   guardadas solo en el navegador).
===================================================================== */
(function(){
  "use strict";
  var PRODUCTION_BACKEND_URL = '';
  var isLocal = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname) || location.protocol === 'file:';
  window.UL_CONFIG = {
    backendUrl: isLocal ? 'http://127.0.0.1:8000' : PRODUCTION_BACKEND_URL
  };
})();
