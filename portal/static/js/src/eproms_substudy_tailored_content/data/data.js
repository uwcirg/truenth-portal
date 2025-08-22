/*
 * properties used by application to persist state
 */
export default {
    userId: false,
    locale: "en-us",
    defaultCountryCode: "US",
    countryCode: "US",
    errorMessage: "",
    currentView: "domain",
    geoIPURL: "//geoip.cirg.washington.edu/json/",
    portalWrapperURL: "/api/portal-wrapper-html/",
    portalFooterURL: "/api/portal-footer-html/",
    domainMappingsURL: "/static/js/src/data/common/empro_domain_mappings.json",
    settingsURL: "/api/settings",
    meURL: "/api/me",
    settings: {},
    userInfo: {},
    userRoles: [],
    LifeRayBaseURL: "",
    domainMappings: {},
    defaultDomain: "default_domain",
    mainPageIdentifiers: ["resource_library", "default_domain"],
    /*
     * tailored domain topics, some for video only, e.g. masculinity & empowerment
     */
    domains: ["mood_changes", "insomnia", "hot_flashes", "sex_and_intimacy", "pain", "fatigue", "masculinity", "empowerment"],
    processedTriggerStates: ["processed", "triggered", "resolved"],
    userDomains: [],
    eligibleCountryCodes: [{
        name: "United Kingdom",
        code: "GB",
        locale: "en_GB"
    },
    {
        name: "Canada",
        code: "CA",
        locale: "en_CA"
    },
    {
        name: "United States",
        code: "US",
        locale: "en_US"
    },
    {
        name: "Australia",
        code: "AU",
        locale: "en_AU"
    }
    ],
    patientRole: "patient",
    //chosen domain
    activeDomain: "",
    domainContent: "",
    getContentAttempt: 0
};
