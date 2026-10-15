import HttpApi from "i18next-http-backend";

async function initI18n(options, callback) {
  const optionsToUse = options ? options : {};
  if (optionsToUse.lng) {
    optionsToUse.lng = optionsToUse.lng.replace(/_/g, "-");
  }
  const lng = optionsToUse.lng || "en-US";
  const sessionStorageKey = `i18nextData_${lng}`;
  const source =
    optionsToUse.loadPath || "/static/files/locales/{{lng}}/translation.json"; //consuming translation json from each corresponding locale
  const defaultOptions = {
    fallbackLng: false,
    lng: "en-US",
    backend: {
      loadPath: source,
      parse: (data) => {
        if (!data) return {};
        const translations = typeof data === "string" ? JSON.parse(data) : data;
        sessionStorage.setItem(sessionStorageKey, JSON.stringify(translations));
        return translations;
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
        "i18nextData_" + optionsToUse.lng,
      );
      //allow lookup for translated text for missing key
      let data;
      try {
        data = sessionItem ? JSON.parse(sessionItem) : null;
      } catch (e) {
        console.log("Error parsing session translation data ", e);
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
      if (err) console.log("Error initializing i18next ", err);
      if (callback) callback();
    }
  );
}

const __i18next = {
  init: initI18n,
};
export default __i18next;
