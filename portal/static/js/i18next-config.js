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
            /*
             * consuming translation json from each corresponding locale
             */
            var source = options.loadPath? options.loadPath : "/static/files/locales/{{lng}}/translation.json";

            i18next.use(i18nextXHRBackend)
                    .use(i18nextBrowserLanguageDetector)
                    .init({
                    /*
                     * language abbrev in underscore format e.g. en_US as set by portal, is not recognized by i18next so need to make sure 
                     * to replace _ with - which it recognizes
                     */
                    fallbackLng: options.fallbackLng ? options.fallbackLng.replace("_", "-") : "en-US",
                    lng: options.lng? options.lng.replace("_", "-"): "en-US",
                    debug: options.debug ? options.debug : (getQueryString["debugi18next"]? true: false),
                    ns: options.ns ? options.ns : ["translation"],
                    defaultNS: "translation",
                    initImmediate: options.initImmediate ? options.initImmediate : false,
                    load: "currentOnly", //this reads language code in en-US, en-AU format
                    returnEmptyString: false,
                    returnNull: false,
                    saveMissing: true,
                    missingKeyHandler: function(lng, ns, key, fallbackValue) {
                        if (options.missingKeyHandler) options.missingKeyHandler(lng, ns, key, fallbackValue);
                    },
                    backend: {
                       // load from static file
                       loadPath: source
                     }
                  }, function(err, t) {
                    if (callback) callback();
                  });
    };

    return {
        init: function(options, callback) { init(options, callback); }
    };
}
)();