/*
 * properties used by application to persist state
 */
export default {
    userId: false,
    locale: "en-us",
    errorMessage: "",
    currentView: "intro",
    portalWrapperURL: "/api/portal-wrapper-html/",
    portalFooterURL: "/api/portal-footer-html/",
    settingsURL: "/api/settings",
    meURL: "/api/me",
    settings: {},
    userInfo: {},
    LifeRayBaseURL: "",
    //TODO add the rest of eligible topics
    domains: ["mood_changes", "insomnia", "hot_flashes", "sex_and_intimacy", "pain", "fatigue"],
    //chosen domain
    activeDomain: "",
    domainContent: "",
    getContentAttempt: 0
};

