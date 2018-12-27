(function() {  /*global $, tnthAjax, SYSTEM_IDENTIFIER_ENUM, i18next */
    var CoreDataObj = function() {
        this.subjectId = 0;
        this.init = function(subjectId) { /* entry point for initiating CoreDataObj */
            var self = this;
            this.setSubjectId(subjectId, function() {
                if (!self.subjectId) {
                    return;
                }
                self.getDemoData();
                self.initFieldEvents();
                self.setFooter();
            });
        };
        this.setSubjectId = function(subjectId, callback) {
            callback = callback || function() {};
            var self = this;
            this.subjectId = subjectId || $("#coreDataUserId").val(); //check user id in template, if any
            if (this.subjectId) {
                callback({success:1});
                return;
            }
            tnthAjax.getCurrentUser(function(data) {
                if (!data || data.error) {
                    self.setError(i18next.t("Error occurred retrieving subject ID"));
                    callback({error: true});
                    return;
                }
                self.subjectId = data.id;
                callback(data);
            });
        };
        this.demoFieldsEnabled = function() {
            return this.getRaceFields().length || this.getEthnicityFields().length;
        };
        this.getRaceFields = function() {
            return $("#userRace input:checkbox");
        };
        this.getEthnicityFields = function() {
            return $("#userEthnicity input:checkbox");
        };
        this.getEthnicityData = function() {
            var ethnicityFields = this.getEthnicityFields().filter(":checked");
            if (!ethnicityFields.length) {
                return false;
            }
            var ethnicityIDs = ethnicityFields.map(function() {
                return {
                    code: $(this).val(),
                    system: SYSTEM_IDENTIFIER_ENUM.ethnicity_system
                };
            }).get();
            return {
                "url": SYSTEM_IDENTIFIER_ENUM.ethnicity,
                "valueCodeableConcept": {"coding": ethnicityIDs}
            };
        };
        this.getRaceData = function() {
            var raceFields = this.getRaceFields().filter(":checked");
            if (!raceFields.length) {
                return false;
            }
            var raceIDs = raceFields.map(function() {
                return {
                    code: $(this).val(),
                    system: SYSTEM_IDENTIFIER_ENUM.race_system
                };
            }).get();
            return {
                "url": SYSTEM_IDENTIFIER_ENUM.race,
                "valueCodeableConcept": {"coding": raceIDs}
            };
        };
        this.setDemoData = function() {
            if (!this.demoFieldsEnabled()) {
                return;
            }
            var raceData = this.getRaceData();
            var ethnicityData = this.getEthnicityData();
            var demoArray = {resourceType: "Patient", extension: []};
            if (raceData) {
                demoArray.extension.push(raceData);
            }
            if (ethnicityData) {
                demoArray.extension.push(ethnicityData);
            }
            tnthAjax.putDemo(this.subjectId, demoArray);
        };
        this.getDemoData = function() {
            if (!this.demoFieldsEnabled()) {
                return;
            }
            tnthAjax.getDemo(this.subjectId);
        };
        this.initDemoFieldEvents = function() {
            if (!this.demoFieldsEnabled()) {
                return;
            }
            var self = this;
            this.getRaceFields().on("click", function() {
                self.setDemoData();
            });
            this.getEthnicityFields().on("click", function() {
                self.setDemoData();
            });
        };
        this.initContinueButtonEvent = function() {
            // Class for both "done" and "skip" buttons
            var self = this;
            $(".continue-btn").on("click", function(event){
                event.preventDefault();
                $(this).attr("disabled", true);
                $(".loading-indicator").show();
                try {
                    window.location.replace(self.getReturnAddress());
                } catch(e) {
                    self.setError(i18next.t("Error occurred when redirecting to destination url"));
                    //report error if invalid return address is used here
                    tnthAjax.reportError(self.subjectId, self.getAPIUrl(), e.message, true);
                    $(this).attr("disabled", false);
                    $(".loading-indicator").hide();
                    $(".error-continue").text(e.message);
                }
            });
        };
        this.initFieldEvents = function() {
            this.initDemoFieldEvents();
            this.initContinueButtonEvent();
        };
        this.getReturnAddress = function() {
            return $("#procReturnAddress").val() || "/";
        };
        this.getAPIUrl = function() {
            return $("procAPIUrl").val() || "/api/coredata/acquire";
        };
        this.setError = function(message) {
            $("#coreDataError").html(message || "");
        };
        this.setFooter = function() { //only for GIL footer
            var self = this;
            tnthAjax.setting("GIL", this.subjectId, false, function(data) {
                if (data && data.GIL) {
                    tnthAjax.getPortalFooter(self.subjectId, false, "core_data_footer");
                }
            });
        };
    };
    $(document).ready(function(){
        (new CoreDataObj()).init();
    });
})();  /*eslint wrap-iife: off */

