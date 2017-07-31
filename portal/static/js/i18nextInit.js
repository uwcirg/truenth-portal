/*** wrapper object to initalize i18next ***/
var __i18next = (function() {
    function init() {
            if (typeof window.localStorage  != "undefined") {
                if (window.localStorage.getItem("i18nextLng")) window.localStorage.removeItem("i18nextLng");
            };
            i18next.use(i18nextXHRBackend)
                    .use(i18nextBrowserLanguageDetector)
                    .init({
                    fallbackLng: 'en-US',
                    //saveMissing: true,
                    // lng: 'en-US',
                    debug: true,
                    ns: ['translation'],
                    defaultNS: 'translation',
                    initImmediate: false,
                    load: 'currentOnly', //this reads language code in en-US, en-AU format
                    returnEmptyString: false,
                    backend: {
                       // load from static file
                       loadPath: '/static/files/locales/{{lng}}/{{ns}}.json'

                     }
                  }, function(err, t) {
                    // init set content
                    //common constants that can be used else where
                    __NOT_PROVIDED_TEXT = i18next.t("Not provided");

                  });
    };

    return {
        init: function() { init(); }
    };
}
)();