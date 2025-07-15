import HttpApi from "i18next-http-backend";

function addQueryString(url, params) {
  if (params && typeof params === "object") {
    let queryString = "",
      e = encodeURIComponent;

    // Must encode data
    for (let paramName in params) {
      queryString += "&" + e(paramName) + "=" + e(params[paramName]);
    }

    if (!queryString) {
      return url;
    }

    url = url + (url.indexOf("?") !== -1 ? "&" : "?") + queryString.slice(1);
  }

  return url;
}

/*** wrapper object to initalize i18next ***/
export default (function () {
  function init(options, callback) {
    var getQueryString = (function (a) {
      if (String(a) === "") {
        return {};
      }
      var b = {};
      for (var i = 0; i < a.length; ++i) {
        var p = a[i].split("=", 2);
        if (p.length === 1) {
          b[p[0]] = "";
        } else {
          b[p[0]] = decodeURIComponent(p[1].replace(/\+/g, " "));
        }
      }
      return b;
    })(window.location.search.substr(1).split("&"));

    if (typeof window.localStorage !== "undefined") {
      if (window.localStorage.getItem("i18nextLng")) {
        window.localStorage.removeItem("i18nextLng");
      }
    }
    var source =
      options.loadPath || "/static/files/locales/{{lng}}/translation.json"; //consuming translation json from each corresponding locale
    var defaultOptions = {
      fallbackLng: "en-US",
      lng: "en-US",
      preload: false,
      debug: false,
      defaultNS: "translation",
      initImmediate: false,
      keySeparator: "----",
      nsSeparator: "----",
      load: "currentOnly",
      returnEmptyString: false,
      returnNull: false,
      saveMissing: false,
      missingKeyHandler: false,
      parseMissingKeyHandler: function (key) {
        //allow lookup for translated text for missing key
        var sessionData = sessionStorage.getItem("i18nextData_" + this.lng);
        if (!sessionData) {
          return key;
        }
        try {
          var data = JSON.parse(sessionData);

          if (data && data.hasOwnProperty(key)) {
            return data[key];
          }
        } catch (e) {
          return key;
        }
        return key;
      },
      backend: {
        // load from static file
        language: options.lng,
        loadPath: source,
        //ajax: function(url, options, callback, data, cache) {
        request: function (options, url, data, callback) {
          /*
           * default code from i18nextBackend.js, but modify it to allow sync loading of resources and add session storage
           */
          callback = callback || function () {};
          options = options ? options : {};
          var sessionItemKey = "i18nextData_" + options.language;
          if (
            data &&
            (typeof data === "undefined" ? "undefined" : _typeof(data)) ===
              "object"
          ) {
            /*global _typeof */
            if (!cache) {
              data["_t"] = new Date();
            }
            // URL encoded form data must be in querystring format
            data = addQueryString("", data).slice(
              1
            ); /* global addQueryString */
          }
          if (options.queryStringParams) {
            url = addQueryString(
              url,
              options.queryStringParams
            ); /* global addQueryString */
          }
          var x;
          if (XMLHttpRequest) {
            x = new XMLHttpRequest();
          } else {
            x = new ActiveXObject(
              "MSXML2.XMLHTTP.3.0"
            ); /*global ActiveXObject */
          }
          try {
            //use sync
            x.open(data ? "POST" : "GET", url, 0);
            if (!options.crossDomain) {
              x.setRequestHeader("X-Requested-With", "XMLHttpRequest");
            }
            x.withCredentials = !!options.withCredentials;
            if (data) {
              x.setRequestHeader(
                "Content-type",
                "application/x-www-form-urlencoded"
              );
            }
            if (x.overrideMimeType) {
              x.overrideMimeType("application/json");
            }
            var h = options.customHeaders;
            if (h) {
              for (var i in h) {
                if (h.hasOwnProperty(i)) {
                  x.setRequestHeader(i, h[i]);
                }
              }
            }
            x.onreadystatechange = function () {
              if (x.readyState > 3) {
                callback(x.responseText, x);
                if (x.responseText && !sessionStorage.getItem(sessionItemKey)) {
                  sessionStorage.setItem(
                    sessionItemKey,
                    JSON.stringify(x.responseText)
                  );
                }
              }
            };
            x.send(data);
          } catch (e) {
            if (console) {
              console.log(e);
            } /*global console */
          }
        },
      },
    };
    options = options || defaultOptions;
    if (options.lng) {
      options.lng = options.lng.replace("_", "-");
    }
    options.debug = options.debug
      ? options.debug
      : getQueryString.debugi18next
      ? true
      : false;
    var configOptions = defaultOptions;
    for (var key in options) {
      if (defaultOptions.hasOwnProperty(key)) {
        defaultOptions[key] = options[key];
      }
    }
    var sessionItemKey = "i18nextData_" + options.language;
    callback = callback || function () {};
    if (typeof i18next === "undefined") {
      //i18next js libraries raises runtime error in <= IE8
      callback();
      return false;
    }
    if (
      String(options.lng).toLowerCase() === "en-us" ||
      sessionStorage.getItem(sessionItemKey)
    ) {
      //still need to initialize i18next but skip call to backend
      i18next.init(configOptions, function (err, t) {
        /* global i18next HttpApi */ callback(t);
      });
    } else {
      i18next.use(HttpApi).init(configOptions, function (err, t) {
        /* global i18next HttpApi */ callback(t);
      });
    }
  }
  return {
    init: function (options, callback) {
      callback = callback || function () {};
      try {
        init(options, callback);
      } catch (e) {
        /*eslint no-console: off */
        console.log("Error initialized i18next ", e.message); //note i18next makes use of session storage/local storage, the access of which creates JS runtime error when cookies are disabled, so we need to catch them
        callback();
      }
    },
  };
})();
