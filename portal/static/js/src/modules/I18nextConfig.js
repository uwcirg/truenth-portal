import HttpApi from "i18next-http-backend";

async function initI18n(options, callback) {
  const optionsToUse = options ? options : {};
  if (optionsToUse.lng) {
    optionsToUse.lng = optionsToUse.lng.replace("_", "-");
  }
  const sessionStorageKey = "i18nextData_" + optionsToUse.lng;
  const source =
    optionsToUse.loadPath || "/static/files/locales/{{lng}}/translation.json"; //consuming translation json from each corresponding locale
  const defaultOptions = {
    fallbackLng: false,
    lng: "en-US",
    backend: {
      loadPath: source,
      parse: (data) => {
        if (!data) return;
        sessionStorage.setItem(
          sessionStorageKey,
          typeof data === "string" ? data : JSON.stringify(data)
        );
      },
    },
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
    parseMissingKeyHandler: (key) => {
      var sessionItem = sessionStorage.getItem(
        "i18nextData_" + optionsToUse.lng
      );
      //allow lookup for translated text for missing key
      let data;
      try {
        data = sessionItem ? JSON.parse(sessionItem) : null;
      } catch (e) {
        console.log("Error parsing session translation data ", sessionData);
        data = null;
      }
      if (!data) {
        return key;
      }
      if (data && data[key]) {
        return data[key];
      }
      return key;
    },
  };
  i18next.use(HttpApi).init(
    {
      ...defaultOptions,
      ...optionsToUse,
    },
    function (err, t) {
      console.log("Error initializing i18next ", err);
      if (callback) callback();
    }
  );
}

const __i18next = {
  init: initI18n,
};
export default __i18next;
