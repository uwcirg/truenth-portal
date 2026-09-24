export var EPROMS_MAIN_STUDY_ID = 0;
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
