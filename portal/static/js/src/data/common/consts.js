export var EPROMS_MAIN_STUDY_ID = 0;
export var EPROMS_SUBSTUDY_ID = 1;
export var EPROMS_SUBSTUDY_TITLE = i18next.t("IRONMAN EMPRO study");
//pre-existing translated text
export var DEFAULT_SERVER_DATA_ERROR = i18next.t("Error retrieving data from server");
/*
Joint and general pain = pain 
Insomnia = insomnia 
Fatigue = fatigue 
Anxious, discouraged, sad, social isolation = mood changes 
*/
//possible domains: 'general_pain', 'joint_pain', 'insomnia', 'fatigue', 'anxious', 'discouraged', 'sad', 'social_isolation'
export var EMPRO_DOMAIN_MAPPINGS = {
    "joint_pain" : "pain",
    "general_pain": "pain",
    "insomnia": "insomnia",
    "anxious": "mood_changes",
    "discouraged": "mood_changes",
    "sad": "mood_changes",
    "social_isolation": "mood_changes",
    "fatigue": "fatigue"
};
