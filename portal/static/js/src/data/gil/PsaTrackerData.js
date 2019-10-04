export default {
    userId: "",
    userIdKey: "psaTracker_currentUser",
    clinicalCode: "666",
    clinicalDisplay: "psa",
    clinicalSystem: "http://us.truenth.org/clinical-codes",
    loginURL: "/user/sign-in?next=/psa-tracker",
    registerURL: "/user/register?next=/psa-tracker",
    loading: false,
    savingInProgress: false,
    addErrorMessage: "",
    MIN_RESULT: 0.1,
    MAX_RESULT: 10000,
    MAX_RANGE_STEP: 9,
    treatmentEditUrl: "profile#profileProceduresWrapper",
    newItem: {
        id: "",
        result: "",
        date: "",
        edit: false
    },
    headers: [
        i18next.t("Date"),
        i18next.t("PSA (ng/ml)")
    ],
    intro: {
        header: i18next.t("Track Your PSA"),
        body: i18next.t("Prostate-specific antigen, or PSA, is a protein produced by cells of the prostate gland. The PSA test measures the level of PSA in a man's blood. For this test, a blood sample is sent to a laboratory for analysis. The results are reported as nanograms of PSA per milliliter (ng/mL) of blood."),
        addText: i18next.t("ADD NEW PSA RESULT")
    },
    fields: {
        resultLabel: i18next.t("PSA (ng/ml)"),
        dateLabel: i18next.t("PSA Test Date"),
        resultPlaceholder: i18next.t("Enter a number"),
        datePlaceholder: i18next.t("d M yyyy, example: 1 Jan, 2017")
    },
    items: [],
    history: {
        title: i18next.t("PSA Result History"),
        items: [],
        buttonLabel: i18next.t("History"),
        sidenote: ""
    },
    modalLoading: false,
    originals: [],
    resultRange: ["<= 4", ">= 2", ">= 3", ">= 4", ">= 5"],
    RANGE_ENUM: {
        "<= 4": function(items) { return $.grep(items, function(item) {
            return item.result <= 4;
        });},
        ">= 2": function(items) { return $.grep(items, function(item) {
            return item.result >= 2;
        });},
        ">= 3": function(items) { return $.grep(items, function(item) {
            return item.result >= 3;
        });},
        ">= 4": function(items) { return $.grep(items, function(item) {
            return item.result >= 4;
        });},
        ">= 5": function(items) { return $.grep(items, function(item) {
            return item.result >= 5;
        });}
    },
    filters: {
        filterYearPrompt: i18next.t("Filter By Year"),
        filterResultPrompt: i18next.t("Filter By Result"),
        selectedFilterYearValue: "",
        selectedFilterResultRange: "",
        clearLabel: i18next.t("Clear Filters")
    },
    showRefresh: false,
    treatment: {
        treatmentTextPrompt: i18next.t("Last Received Treatment:"),
        treatmentDatePrompt: i18next.t("Treatment Date:"),
        noTreatmentText: i18next.t("No treatment received as of today"),
        data: []
    },
    PSALabel: i18next.t("PSA"),
    loginLabel: i18next.t("Login"),
    loginPrompt: i18next.t("<a data-toggle='modal' data-target='#psaLoginRegisterModal'>Login or Register</a> now to track and store your PSA"),
    joinUsText: i18next.t("Join Us"),
    createAccountText: i18next.t("Create Account"),
    createAccountIntroText: i18next.t("It’s going to take a group effort to improve the prostate cancer experience for future generations."),
    noResultMessage: i18next.t("No PSA results to display"),
    editText: i18next.t("Edit"),
    saveText: i18next.t("Save"),
    closeText: i18next.t("Close"),
    filterText: i18next.t("Filter"),
    yLegendText: i18next.t("Result (ng/ml)"),
    xLegendText: i18next.t("PSA Test Date"),
    treatmentLabel: i18next.t("treatment"),
    editLink: i18next.t("Edit"),
    editTitle: i18next.t("Edit PSA Result"),
    addTitle: i18next.t("Add PSA Result"),
    refreshErrorMessage: i18next.t("Click to reload the page and try again."),
    resultValidationErrorMessage: i18next.t("Result must be a number and within valid range (less than {max_result})."),
    dateValidationErrorMessage: i18next.t("Date must be in the valid format."),
    serverErrorMessage: i18next.t("Error occurred retrieving PSA result data"),
    noDataErrorMessage: i18next.t("No result data found"),
    historySideNote: i18next.t("* Maximum of {resultNumber} results since {year}"),
    nullResultMessage: i18next.t("No PSA results to display"),
    nullFilterResultMessage: i18next.t("No PSA result matching the filtering criteria. Please try again."),
    addServerErrorMessage: i18next.t("Server error occurred adding PSA result.")
};
