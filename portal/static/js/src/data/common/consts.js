export var EPROMS_MAIN_STUDY_ID = 0;
export var EPROMS_SUBSTUDY_ID = 1;
export var EPROMS_SUBSTUDY_SHORT_TITLE = "EMPRO";
export var EPROMS_SUBSTUDY_TITLE = i18next.t("IRONMAN EMPRO study");
export var EMPRO_TRIGGER_PROCCESSED_STATES = [
  "processed",
  "triggered",
  "resolved",
];
export var EMPRO_TRIGGER_UNPROCCESSED_STATES = [
  "due",
  "inprocess",
  "unstarted",
];
export var EMPRO_TRIGGER_PRESTATE = "unstarted"; // see /trigger_states/empro_states.py for explanation of different trigger states
export var EPROMS_SUBSTUDY_QUESTIONNAIRE_IDENTIFIER = "ironman_ss";
export var EMPRO_POST_TX_QUESTIONNAIRE_IDENTIFIER = "ironman_ss_post_tx";
//pre-existing translated text
export var DEFAULT_SERVER_DATA_ERROR = i18next.t(
  "Error retrieving data from server"
);
export var REQUIRED_PI_ROLES = ["staff", "staff_admin", "clinician"];
export var REQUIRED_PI_ROLES_WARNING_MESSAGE =
  i18next.t(`<p>An account with a Primary Investigator role must also have at least ONE of the following roles:</p>
            <ul>
                <li><b>Staff</b></li>
                <li><b>Admin Staff</b></li>
                <li><b>Clinician</b></li>
            </ul>`);
