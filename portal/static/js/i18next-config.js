/*** wrapper object to initalize i18next ***/
var __i18next = (function() {
    function init(options, callback) {
            if (typeof window.localStorage  != "undefined") {
                if (window.localStorage.getItem("i18nextLng")) window.localStorage.removeItem("i18nextLng");
            };
            if (!options) options = {};
            var source = options.loadPath? options.loadPath : '/static/files/locales/{{lng}}/translation.json';

            i18next.use(i18nextXHRBackend)
                    .use(i18nextBrowserLanguageDetector)
                    .init({
                    fallbackLng: options.fallbackLng ? options.fallbackLng : 'en-US',
                    //saveMissing: true,
                    // lng: 'en-US',
                    debug: options.debug ? options.debug : true,
                    ns: options.ns ? options.ns : ['translation'],
                    defaultNS: 'translation',
                    initImmediate: options.initImmediate ? options.initImmediate : false,
                    load: 'currentOnly', //this reads language code in en-US, en-AU format
                    returnEmptyString: false,
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