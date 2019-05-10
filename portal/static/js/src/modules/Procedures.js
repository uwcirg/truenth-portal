import tnthAjax from "./TnthAjax.js";
import tnthDates from "./TnthDate.js";
import Utility from "./Utility.js";
import SYSTEM_IDENTIFIER_ENUM from "./SYSTEM_IDENTIFIER_ENUM.js";
export default (function() {
    /*global $ i18next tnthAjax tnthDates SYSTEM_IDENTIFIER_ENUM */
    var ProcApp = {
        subjectId: "",
        currentUserId: "",
        dateFields: ["procDay", "procMonth", "procYear"],
        entries: [],
        initCounts: 0,
        init: function(subjectId) { //entry method for initializing ProcApp object
            var self = this;
            this.initUserIds(subjectId, function() {
                if (!self.subjectId) {
                    self.setError(i18next.t("Subject id is required")); //display error on UI
                    return false;
                }
                self.getOptions(); //treatment options
                self.getUserProcedures();
                self.initFieldExtension();
                self.initFieldEvents();
            });
        },
        initViaTemplate: function() { //profile and coredata views
            var self = this;
            $(document).ready(function() {
                var profileSubject = $("#profileProcSubjectId");
                if (!profileSubject.length) {
                    return;
                }
                self.init(profileSubject.val());
            });
        },
        initUserIds: function(subjectId, callback) {
            callback = callback || function() {};
            var self = this;
            this.setSubjectId(subjectId);
            tnthAjax.getCurrentUser(function(data) {
                if (!data || data.error) {
                    self.setError(i18next.t("error occurred setting current user id"));
                    callback();
                    return;
                }
                self.setCurrentUserId(data.id);
                if (!self.subjectId) {
                    self.setSubjectId(data.id);
                }
                callback();
            });
        },
        setSubjectId: function(id) {
            this.subjectId = id;
        },
        setCurrentUserId: function(id) {
            this.currentUserId = id;
        },
        setError: function(message) {
            $("#procDateErrorContainer").html(message||"");
            if (message) {
                $("#procedure_view").html("<p class='text-muted'>" + i18next.t("no data found") + "</p>");
            }
        },
        setTreatmentOptionsSelector: function(entries) {
            if (!entries) {
                return;
            }
            var optionsList = [];
            optionsList.push("<option value=''>" + i18next.t("Select") + "</option>");
            entries.forEach(function(item) {
                optionsList.push("<option value='{value}' data-system='{system}'>{text}</option>"
                    .replace("{value}", item.code)
                    .replace("{text}", item.text)
                    .replace("{system}", item.system));
            });
            $("#tnthproc").append(optionsList.join(""));
            sessionStorage.setItem("treatmentOptions", JSON.stringify(entries));
        },
        getOptions: function() {
            if (!$("#tnthproc").length) {
                return;
            }
            if (sessionStorage.treatmentOptions) {
                this.setTreatmentOptionsSelector(JSON.parse(sessionStorage.treatmentOptions));
                return;
            }
            var self = this, url =  "/patients/treatment-options";
            if (window.Worker) {
                Utility.initWorker(url, {cache: true}, function(result) { /*global Utility */
                    var data = JSON.parse(result);
                    self.setTreatmentOptionsSelector(data.treatment_options);
                });
                return true;
            }
            $.ajax({
                type: "GET",
                url: url,
                cache: true
            }).done(function(data) {
                self.setTreatmentOptionsSelector(data.treatment_options);
            }).fail(function() {});
        },
        getCreatorDisplay: function(creator, defaultDisplay) {
            if (!creator) {
                return "";
            }
            if (String(creator) === this.currentUserId) {
                return i18next.t("you");
            } else if (String(creator) === String(this.subjectId)) {
                return i18next.t("this patient");
            }
            return i18next.t("staff member") + ", <span class='creator'>" + defaultDisplay + "</span>, ";
        },
        getDeleteInvocationDisplay: function() {
            return $("#popoverHolder .popover__link").html();
        },
        setNewEntry: function(newEntry, highestId){
            if (!newEntry) {
                return;
            }
            // If newEntry, then add icon to what we just added
            $("#eventListtnthproc").find("tr[data-id='" + highestId + "'] td.descriptionCell").append("&nbsp; <small class='text-success'><i class='fa fa-check-square-o'></i> <em>" + i18next.t("Added!") + "</em></small>");
        },
        setProcedureRowsView: function() {
            var content = "";
            $("#userProcedures tr[data-id]").each(function() {
                $(this).find("td").each(function() {
                    if (!$(this).hasClass("list-cell") && !$(this).hasClass("lastCell")) {
                        content += "<div>" + $(this).text() + "</div>"; //display content from database
                    }
                });
            });
            $("#procedure_view").html(content || ("<p class='text-muted'>" + i18next.t("no data found") + "</p>"));
        },
        setNoDataDisplay: function() {
            $("#userProcedures").html("<p id='noEvents'><em>" + i18next.t("You haven't entered any management option yet.") + "</em></p>").animate({
                opacity: 1
            });
            $("#procedure_view").html("<p class='text-muted'>" + i18next.t("no data found") + "</p>");
            $("#pastTreatmentsContainer").hide();
            $("#eventListLoad").fadeOut();
        },
        getUserProcedures: function(newEntry) {
            if (!this.subjectId) {
                return false;
            }
            var self = this;
            $.ajax({
                type: "GET",
                url: "/api/patient/" + this.subjectId + "/procedure",
                cache: false
            }).done(function(data) {
                if (data.entry.length === 0) {
                    self.setNoDataDisplay();
                    return false;
                }
                self.onDidGetProcedures(data.entry, newEntry);
                $("#eventListLoad").fadeOut();
            }).fail(function() {
                self.setError(i18next.t("error occurred retrieving user procedures"));
                $("#eventListLoad").fadeOut();
            });
        },
        initFieldEvents: function() {
            var self = this;

            this.convertToNumericField($("#procYear, #procDay"));

            setTimeout(function() {// Trigger eventInput on submit button
                $("#tnthproc-submit").eventInput();
            }, 150);

            $("#tnthproc").on("change", function() { // Update submit button when select changes
                $("#tnthproc-submit").attr({"data-name": $(this).val(), "data-system": $(this).find("option:selected").attr("data-system")});
                self.checkSubmit("#tnthproc-submit");
            });

            self.dateFields.forEach(function(fn) {
                $("#" + fn).on("keyup change", function() {
                    self.setDate();
                });
            });

            $("body").on("click", ".data-delete", function() { //new row remove button event at account creation
                $(this).closest("tr").remove();
            });
        },
        initPopoverEvents: function() {
            var self = this;
            $("[data-toggle='popover']").popover({trigger: "click", placement: "top", html: true, content: $("#popoverHolder .popover__content").html()});
            $("body").on("click", ".cancel-delete", function(e) { //popover cancel button event
                e.stopImmediatePropagation();
                $(this).parents("div.popover").prev("a.confirm-delete").trigger("click");
            });

            $("body").on("click", ".btn-delete", function() { // popover delete button event - need to attach delete functionality to body b/c section gets reloaded
                var procId = $(this).parents("tr").attr("data-id");
                $(this).parents("tr").fadeOut("slow", function() {
                    $(this).remove(); // Remove from list
                    if ($("#eventListtnthproc tr").length === 0) { //If there's no events left, add status msg back in
                        self.setNoDataDisplay();
                    }
                });
                tnthAjax.deleteProc(procId, false, false, function() { // Post delete to server
                    self.getUserProcedures();
                });
                return false;
            });
        },
        onDidGetProcedures: function(data, newEntry) {
            this.populateProcedureRows(data, newEntry);
            this.setProcedureRowsView();
            this.setError(!data||data.error?i18next("Error occurred retrieving procedures"): "");
        },
        populateProcedureRows: function(data, newEntry) {
            data.sort(function(a, b) { // sort from newest to oldest
                return new Date(b.resource.performedDateTime) - new Date(a.resource.performedDateTime);
            });
            var self = this, contentHTML = [], proceduresHtml = "", otherHtml = [];
            // If we're adding a procedure in-page, then identify the highestId (most recent) so we can put "added" icon
            var highestId = 0;
            $.each(data, function(i, val) {
                var code = val.resource.code.coding[0].code;
                var procID = val.resource.id;
                if ([SYSTEM_IDENTIFIER_ENUM.CANCER_TREATMENT_CODE, SYSTEM_IDENTIFIER_ENUM.NONE_TREATMENT_CODE].indexOf(code) !== -1) {
                    //for entries marked as other procedure.  These are rendered as hidden fields and can be referenced when these entries are deleted.
                    otherHtml.push("<input type='hidden' data-id='" + procID + "'  data-code='" + code + "' name='otherProcedures' >");
                    return true;
                }
                var creatorRef = (val.resource.meta.by.reference).match(/\d+/)[0];  // just the user ID, not eg "api/patient/46";
                var creator = self.getCreatorDisplay(creatorRef, val.resource.meta.by.display || creatorRef);
                var dateEdited = new Date(val.resource.meta.lastUpdated);
                var creationText = i18next.t("(data entered by {actor} on {date})").replace("{actor}", creator).replace("{date}", dateEdited.toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "short",
                    year: "numeric"
                }));
                var deleteInvocation = "";
                if (String(creatorRef) === String(self.currentUserId)) {
                    deleteInvocation = self.getDeleteInvocationDisplay();
                }
                contentHTML.push(["<tr data-id='" + procID + "' data-code='" + code + "'>",
                    "<td width='1%' valign='top' class='list-cell'>&#9679;</td>",
                    "<td class='col-md-10 col-xs-10 descriptionCell' valign='top'>" +
                    (tnthDates.formatDateString(val.resource.performedDateTime)) + "&nbsp;--&nbsp;" + val.resource.code.coding[0].display +
                    "&nbsp;<em>" + creationText +
                    "</em></td>",
                    "<td class='col-md-2 col-xs-2 lastCell text-left' valign='top'>" +
                    deleteInvocation + "</td>",
                    "</tr>"].join(""));
                highestId = Math.max(highestId, procID);
            });
            if (contentHTML) {
                proceduresHtml = "<table  class=\"table-responsive\" width=\"100%\" id=\"eventListtnthproc\" cellspacing=\"4\" cellpadding=\"6\">";
                proceduresHtml += contentHTML.join("");
                proceduresHtml += "</table>";
                $("#userProcedures").html(proceduresHtml);
            }
            this.setNewEntry(newEntry, highestId);
            this.initPopoverEvents();

            if ($("#eventListtnthproc tr").length) {
                $("#pastTreatmentsContainer").fadeIn();
            } else {
                $("#pastTreatmentsContainer").fadeOut();
            }

            $("#userProcedures").append(otherHtml.join("")); //other procedures
        },
        handleOtherProcedures: function() {
            var otherProcElements = $("#userProcedures input[name='otherProcedures']");
            if (!otherProcElements.length) {
                return false;
            }
            otherProcElements.each(function() {
                var code = $(this).attr("data-code"), procId = $(this).attr("data-id");
                if ([SYSTEM_IDENTIFIER_ENUM.CANCER_TREATMENT_CODE, SYSTEM_IDENTIFIER_ENUM.NONE_TREATMENT_CODE].indexOf(code) !== -1) { //remove any procedure on prostate or none treatment
                    tnthAjax.deleteProc(procId);
                }
            });
        },
        setAccountCreationRowDisplay: function(procArray) {
            procArray = procArray || {};
            if ($("#pastTreatmentsContainer tr[data-code='" + procArray["code"] + "'][data-performedDateTime='" + procArray["performedDateTime"] + "']").length === 0) {
                var content = [];
                content.push("<tr ");
                var arrProcAttrs = [];
                for (var item in procArray) { /*eslint guard-for-in: off, security/detect-object-injection: off */
                    arrProcAttrs.push("data-" + item + "='" + procArray[item] + "'");
                }
                content.push(arrProcAttrs.join(" "));
                content.push(">");
                content.push("<td>&#9679;</td><td>" + procArray["display"] + "</td><td>" + procArray["performedDateTime"] + "</td><td><a class='btn btn-default btn-xs data-delete'>" + i18next.t("REMOVE") + "</a></td>");
                content.push("</tr>");
                $("#pastTreatmentsContainer").append(content.join(""));
                setTimeout(function() {
                    $("#pastTreatmentsContainer").show();
                }, 100);
            }
        },
        initFieldExtension: function() {
            var self = this;
            $.fn.extend({
                // Special type of select question - passes two values - the answer from - the select plus an associated date from a separate input
                eventInput: function() {
                    $(this).on("click", function(e) {
                        e.stopImmediatePropagation();
                        $(this).attr("disabled", true); // First disable button to prevent double-clicks
                        var isAccountCreation = $(this).attr("data-account-create");
                        var subjectId = self.subjectId, selectVal = $(this).attr("data-name"), selectDate = $(this).attr("data-date"), selectSystem = $(this).attr("data-system");
                        if (!selectVal || !selectDate) {
                            return false;
                        }
                        var selectFriendly = $("#tnthproc option:selected").text();
                        var procArray = {resourceType: "Procedure", performedDateTime: selectDate, system: selectSystem};
                        /* eslint detect-object-injection: off*/
                        if (isAccountCreation) {
                            procArray["display"] = selectFriendly;
                            procArray["code"] = selectVal;
                            self.setAccountCreationRowDisplay(procArray);
                        } else {
                            self.handleOtherProcedures();
                            var procID = [{"code": selectVal, "display": selectFriendly, system: selectSystem}];
                            procArray["subject"] = {"reference": "Patient/" + subjectId};
                            procArray["code"] = { "coding": procID};
                            $(".update-subscriber").trigger("pre-update");
                            tnthAjax.postProc(subjectId, procArray,"", function(data) {
                                if (data && data.error) {
                                    $("#procErrorMessage").html(data.error);
                                }
                                $(".update-subscriber").trigger("post-update");
                            });
                            $("#eventListLoad").show();
                            setTimeout(function() { // Set a delay before getting updated list. Mostly to give user sense of progress/make it more obvious when the updated list loads
                                self.getUserProcedures(true);
                            }, 1800);
                            $("#pastTreatmentsContainer").hide();
                        }
                        self.reset();
                        return false;
                    });
                }
            }); // $.fn.extend({
        },
        reset: function() {
            $("#tnthproc").val(""); //treatment select element
            $("#procDay, #procMonth, #procYear").val(""); //date fields
            $("#tnthproc-submit").addClass("disabled").attr({"data-name": "", "data-date": "", "data-date-read": "", "data-system": ""}); // Clear submit button
        },
        checkSubmit: function(btnId) { // Add/remove disabled from submit button
            if (String($(btnId).attr("data-name")) !== "" && String($(btnId).attr("data-date-read")) !== "") {
                $(btnId).removeClass("disabled").removeAttr("disabled");
            } else {
                $(btnId).addClass("disabled").attr("disabled", true);
            }
        },
        convertToNumericField: function(field) {
            if ("ontouchstart" in window || (typeof window.DocumentTouch !== "undefined" && document instanceof window.DocumentTouch)) {
                $(field).each(function() {
                    $(this).prop("type", "tel");
                });
            }
        },
        isTouchScreen: function() {
            return ("ontouchstart" in window || window.DocumentTouch && document instanceof window.DocumentTouch);
        },
        checkDate: function() {
            var df = $("#procDay"), mf =  $("#procMonth"), yf = $("#procYear");
            var d = df.val(), y = yf.val();
            var deField = $("#procDateErrorContainer"), errorClass="error-message";
            if (!d || !/(19|20)\d{2}/.test(y)) {
                return false;
            }
            if (!tnthDates.validateDateInputFields(mf.val(), df.val(), yf.val(), "procDateErrorContainer")) {
                deField.text(i18next.t("The procedure date must be valid and in required format.")).addClass(errorClass);
                return false;
            }
            deField.text("").removeClass(errorClass);
            return true;
        },
        setDate: function() {
            var isValid = this.checkDate();
            if (isValid) {
                var passedDate = this.dateFields.map(function(fn) {
                    return $("#" + fn).val();
                }).join("/");
                $("#tnthproc-submit").attr("data-date-read", passedDate);
                $("#tnthproc-submit").attr("data-date", tnthDates.swap_mm_dd(passedDate));
            } else {
                $("#tnthproc-submit").attr({"data-date-read": "", "data-date": ""});
            }
            this.checkSubmit("#tnthproc-submit");
        }
    };
    return ProcApp;
})(); /*eslint wrap-iife: off */
