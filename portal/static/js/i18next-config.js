/*** wrapper object to initalize i18next ***/
var __i18next = window.__i18next = (function() {
    function init(options, callback) {
            var getQueryString = (function(a) {
            if (a == "") return {};
            var b = {};
            for (var i = 0; i < a.length; ++i)
            {
                var p=a[i].split('=', 2);
                if (p.length == 1)
                    b[p[0]] = "";
                else
                    b[p[0]] = decodeURIComponent(p[1].replace(/\+/g, " "));
            }
            return b;
            })(window.location.search.substr(1).split('&'));

            if (typeof window.localStorage  != "undefined") {
                if (window.localStorage.getItem("i18nextLng")) window.localStorage.removeItem("i18nextLng");
            };
            if (!options) options = {};
            if (options.lng) options.lng = options.lng.replace("_", "-");
            /*
             * consuming translation json from each corresponding locale
             */
            var source = options.loadPath? options.loadPath : "/static/files/locales/{{lng}}/translation.json";

            i18next.use(i18nextXHRBackend)
                    .use(i18nextBrowserLanguageDetector)
                    .init({
                        fallbackLng: options.fallbackLng ? options.fallbackLng.replace("_", "-") : "en-US",
                        lng: options.lng? options.lng: "en-US",
                        preload: options.lng? [options.lng] : false,
                        debug: options.debug ? options.debug : (getQueryString["debugi18next"]? true: false),
                        ns: options.ns ? options.ns : ["translation"],
                        defaultNS: "translation",
                        initImmediate: options.initImmediate ? options.initImmediate : false,
                        keySeparator: "----",
                        nsSeparator: "----",
                        load: "currentOnly", //this reads language code in en-US, en-AU format
                        returnEmptyString: false,
                        returnNull: false,
                        saveMissing: true,
                        missingKeyHandler: function(lng, ns, key, fallbackValue) {
                            if (options.missingKeyHandler) options.missingKeyHandler(lng, ns, key, fallbackValue);
                        },
                        parseMissingKeyHandler: function(key) {
                            /*
                             * allow lookup for translated text for missing key
                             */
                            var sessionData = sessionStorage.getItem("i18nextData_"+this.lng);
                            if (sessionData) {
                                var data;

                                try {
                                    data = JSON.parse(sessionData);
                                    if (data && data[key]) return data[key];
                                } catch(e) {
                                    return key;
                                }
                            }
                            return key;
                        },
                        backend: {
                            // load from static file
                            language: options.lng,
                            loadPath: source,
                            ajax: function(url, options, callback, data, cache) {
                                /*
                                 * default code from i18nextBackend.js, but modify it to allow sync loading of resources and add session storage
                                 */
                                var sessionItemKey = "i18nextData_"+options.language;

                                if (data && (typeof data === 'undefined' ? 'undefined' : _typeof(data)) === 'object') {
                                    if (!cache) {
                                        data['_t'] = new Date();
                                    }
                                    // URL encoded form data must be in querystring format
                                    data = addQueryString('', data).slice(1);
                                }

                                if (options.queryStringParams) {
                                    url = addQueryString(url, options.queryStringParams);
                                }

                                try {
                                    var x;
                                    if (XMLHttpRequest) {
                                        x = new XMLHttpRequest();
                                    } else {
                                        x = new ActiveXObject('MSXML2.XMLHTTP.3.0');
                                    }
                                    //use sync
                                    x.open(data ? 'POST' : 'GET', url, 0);
                                    if (!options.crossDomain) {
                                        x.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                                    }
                                    x.withCredentials = !!options.withCredentials;
                                    if (data) {
                                        x.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
                                    }
                                    if (x.overrideMimeType) {
                                        x.overrideMimeType("application/json");
                                    }
                                    var h = options.customHeaders;
                                    if (h) {
                                      for (var i in h) {
                                        x.setRequestHeader(i, h[i]);
                                      }
                                    }
                                    x.onreadystatechange = function () {
                                        if (x.readyState > 3 && x.responseText && !sessionStorage.getItem(sessionItemKey)) {
                                            sessionStorage.setItem(sessionItemKey, JSON.stringify(x.responseText));
                                        }
                                        x.readyState > 3 && callback && callback(x.responseText, x);
                                    };
                                    x.send(data);
                                } catch (e) {
                                    console && console.log(e);
                                }
                            }
                        }
                  }, function(err, t) {
                    if (callback) callback(t);
                  });
    };

    return {
        init: function(options, callback) { init(options, callback); }
    };
}
)();