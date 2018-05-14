(function() {
    //TODO this JS code file needs a bit of clean-up
    /*global $ */
    var i18next = window.portalModules.i18next, tnthAjax = window.portalModules.tnthAjax, tnthDates = window.portalModules.tnthDates, SYSTEM_IDENTIFIER_ENUM = window.portalModules.SYSTEM_IDENTIFIER_ENUM;
    var procDateReg = /(0[1-9]|1\d|2\d|3[01])/;
    var procYearReg = /(19|20)\d{2}/;
    var dateFields = ["procDay", "procMonth", "procYear"];
    var procApp = {
        subjectId: $("#profileProcSubjectId").val(),
        currentUserId: $("#profileProcCurrentUserId").val(),
        entries: [],
        initCounts: 0,
        init: function() {
            if ($("#profileProcedureContainer").length > 0) {
                this.getOptions();
                this.getUserProcedures();
            }
        },
        updateTreatmentOptions: function(entries) {
            if (entries) {
                $("#tnthproc").append("<option value=''>" + i18next.t("Select") + "</option>");
                entries.forEach(function(item) {
                    $("#tnthproc").append("<option value='{value}' data-system='{system}'>{text}</option>"
                        .replace("{value}", item.code)
                        .replace("{text}", i18next.t(item.text))
                        .replace("{system}", item.system));
                });
            }
        },
        getOptions: function() {
            var self = this;
            $.ajax({
                type: "GET",
                url: "/patients/treatment-options",
                cache: true
            }).done(function(data) {
                if (sessionStorage.treatmentOptions) {
                    self.updateTreatmentOptions(JSON.parse(sessionStorage.treatmentOptions));
                } else {
                    if (data.treatment_options) {
                        sessionStorage.setItem("treatmentOptions", JSON.stringify(data.treatment_options));
                        self.updateTreatmentOptions(data.treatment_options);
                    }
                }
            }).fail(function() {});
        },
        getUserProcedures: function(newEntry) {
            if (!this.subjectId) {
                return false;
            }
            $.ajax({
                type: "GET",
                url: "/api/patient/" + this.subjectId + "/procedure",
                cache: false
            }).done(function(data) {
                if (data.entry.length === 0) {
                    $("#userProcedures").html("<p id='noEvents' style='margin: 0.5em 0 0 1em'><em>" + i18next.t("You haven't entered any management option yet.") + "</em></p>").animate({
                        opacity: 1
                    });
                    $("#procedure_view").html("<p class='text-muted'>" + i18next.t("no data found") + "</p>");
                    $("#pastTreatmentsContainer").hide();
                    return false;
                }
                data.entry.sort(function(a, b) { // sort from newest to oldest
                    return new Date(b.resource.performedDateTime) - new Date(a.resource.performedDateTime);
                });
                var contentHTML = "", proceduresHtml = "", otherHtml = "";
                // If we're adding a procedure in-page, then identify the highestId (most recent) so we can put "added" icon
                var highestId = 0, currentUserId = $("#profileProcCurrentUserId").val(), subjectId = $("#profileProcSubjectId").val();
                $.each(data.entry, function(i, val) {
                    var code = val.resource.code.coding[0].code;
                    var procID = val.resource.id;
                    if (code !== SYSTEM_IDENTIFIER_ENUM.CANCER_TREATMENT_CODE && code !== SYSTEM_IDENTIFIER_ENUM.NONE_TREATMENT_CODE) {
                        var displayText = val.resource.code.coding[0].display;
                        var performedDateTime = val.resource.performedDateTime;
                        var deleteInvocation = "";
                        var creatorDisplay = val.resource.meta.by.display;
                        var creator = val.resource.meta.by.reference;
                        creator = creator.match(/\d+/)[0]; // just the user ID, not eg "api/patient/46";
                        if (String(creator) === String(currentUserId)) {
                            creator = i18next.t("you");
                            deleteInvocation = "  <a data-toggle='popover' class='btn btn-default btn-xs confirm-delete' data-content='" + i18next.t("Are you sure you want to delete this treatment?") + "<br /><br /><a href=\"#\" class=\"btn-delete btn btn-tnth-primary\" style=\"font-size:0.95em\">" + i18next.t("Yes") + "</a> &nbsp;&nbsp;&nbsp; <a class=\"btn cancel-delete\" style=\"font-size: 0.95em\">" + i18next.t("No") + "</a>' rel='popover'><i class='fa fa-times'></i> " + i18next.t("Delete") + "</span>";
                        } else if (String(creator) === String(subjectId)) {
                            creator = i18next.t("this patient");
                        } else {
                            creator = i18next.t("staff member") + ", <span class='creator'>" + (creatorDisplay ? creatorDisplay : creator) + "</span>, ";
                        }
                        var dtEdited = val.resource.meta.lastUpdated, dateEdited = new Date(dtEdited);
                        var creationText = i18next.t("(date entered by %actor on %date)").replace("%actor", creator).replace("%date", dateEdited.toLocaleDateString("en-GB", {
                            day: "numeric",
                            month: "short",
                            year: "numeric"
                        }));
                        contentHTML += "<tr data-id='" + procID + "' data-code='" + code + "'><td width='1%' valign='top' class='list-cell'>&#9679;</td><td class='col-md-10 col-xs-10 descriptionCell' valign='top'>" +
                            (tnthDates.formatDateString(performedDateTime)) + "&nbsp;--&nbsp;" + displayText +
                            "&nbsp;<em>" + creationText +
                            "</em></td><td class='col-md-2 col-xs-2 lastCell text-left' valign='top'>" +
                            deleteInvocation + "</td></tr>";
                        if (procID > highestId) {
                            highestId = procID;
                        }
                    } else { //for entries marked as other procedure.  These are rendered as hidden fields and can be referenced when these entries are deleted.
                        otherHtml += "<input type='hidden' data-id='" + procID + "'  data-code='" + code + "' name='otherProcedures' >";
                    }
                });

                if (contentHTML) {
                    proceduresHtml = '<table  class="table-responsive" width="100%" id="eventListtnthproc" cellspacing="4" cellpadding="6">';
                    proceduresHtml += contentHTML;
                    proceduresHtml += "</table>";
                    $("#userProcedures").html(proceduresHtml);
                    $("#pastTreatmentsContainer").fadeIn();
                } else {
                    $("#pastTreatmentsContainer").fadeOut();
                }

                if (otherHtml) {
                    $("#userProcedures").append(otherHtml);
                }

                if (newEntry) { //// If newEntry, then add icon to what we just added
                    $("#eventListtnthproc").find("tr[data-id='" + highestId + "'] td.descriptionCell").append("&nbsp; <small class='text-success'><i class='fa fa-check-square-o'></i> <em>" + i18next.t("Added!") + "</em></small>");
                }
                $('[data-toggle="popover"]').popover({trigger: "click", placement: "top", html: true});

                var content = "";
                $("#userProcedures tr[data-id]").each(function() {
                    $(this).find("td").each(function() {
                        if (!$(this).hasClass("list-cell") && !$(this).hasClass("lastCell")) {
                            content += "<div>" + i18next.t($(this).text()) + "</div>";
                        }
                    });
                });
                $("#procedure_view").html(content || ("<p class='text-muted'>" + i18next.t("no data found") + "</p>"));
                $("#eventListLoad").fadeOut();
            }).fail(function() {
                $("#procDateErrorContainer").html(i18next.t("error ocurred retrieving user procedures"));
                $("#procedure_view").html("<p class='text-muted'>" + i18next.t("no data found") + "</p>");
                $("#eventListLoad").fadeOut();
            });
        }
    };
    $.fn.extend({
        // Special type of select question - passes two values - the answer from - the select plus an associated date from a separate input
        eventInput: function(settings) {
            if (!settings) {
                settings = {};
            }
            var tnthAjax = settings["tnthAjax"]; //this will error out if not defined

            $(this).on("click", function(e) {
                e.stopImmediatePropagation();
                $(this).attr("disabled", true); // First disable button to prevent double-clicks
                var isAccountCreation = $(this).attr("data-account-create");
                var subjectId = $("#profileProcSubjectId").val(), selectVal = $(this).attr("data-name"), selectDate = $(this).attr("data-date"), selectSystem = $(this).attr("data-system");
                if (selectVal !== undefined && selectDate !== undefined) {
                    var selectFriendly = $("#tnthproc option:selected").text();
                    var procArray = {};
                    procArray["resourceType"] = "Procedure";
                    procArray["performedDateTime"] = selectDate;
                    procArray["system"] = selectSystem;

                    if (isAccountCreation) {
                        if ($("#pastTreatmentsContainer tr[data-code='" + selectVal + "'][data-performedDateTime='" + selectDate + "']").length === 0) {
                            procArray["display"] = selectFriendly;
                            procArray["code"] = selectVal;
                            var content = "";
                            content += "<tr ";
                            for (var item in procArray) {
                                content += " data-" + item + "='" + procArray[item] + "'";
                            }
                            content += ">";
                            content += "<td>&#9679;</td><td>" + selectFriendly + "</td><td>" + selectDate + "</td><td><a class='btn btn-default btn-xs data-delete'>" + i18next.t("REMOVE") + "</a></td>";
                            content += "</tr>";
                            $("#pastTreatmentsContainer").append(content);
                            setTimeout(function() {
                                $("#pastTreatmentsContainer").show();
                            }, 100);
                        }

                    } else {
                        //remove any procedure on prostate or none treatment
                        var otherProcElements = $("#userProcedures input[name='otherProcedures']");
                        if (otherProcElements.length > 0) {
                            otherProcElements.each(function() {
                                var code = $(this).attr("data-code"), procId = $(this).attr("data-id");
                                if (code === SYSTEM_IDENTIFIER_ENUM.CANCER_TREATMENT_CODE) {
                                    tnthAjax.deleteProc(procId);
                                }
                                if (code === SYSTEM_IDENTIFIER_ENUM.NONE_TREATMENT_CODE) {
                                    tnthAjax.deleteProc(procId);
                                }
                            });
                        }

                        var procID = [{
                            "code": selectVal,
                            "display": selectFriendly,
                            system: selectSystem
                        }];
                        procArray["subject"] = {"reference": "Patient/" + subjectId};
                        procArray["code"] = { "coding": procID};
                        tnthAjax.postProc(subjectId, procArray);

                        // Update the procedure list - we animate opacity to retain the
                        // width and height so lower content doesn't go up and down
                        $("#eventListLoad").show();

                        // Set a one second delay before getting updated list. Mostly to give user sense of progress/make it
                        // more obvious when the updated list loads
                        setTimeout(function() {
                            procApp.getUserProcedures(true);
                        }, 1800);
                        $("#pastTreatmentsContainer").hide();
                    }

                    $("select[id^='tnthproc']").val("");
                    $("input[id^='tnthproc-value']").val("");
                    $("input[id^='tnthproc-date']").val("");
                    $("#procDay").val("");
                    $("#procMonth").val("");
                    $("#procYear").val("");
                    // Clear submit button
                    $("button[id^='tnthproc-submit']").addClass("disabled").attr({
                        "data-name": "",
                        "data-date": "",
                        "data-date-read": "",
                        "data-system": ""
                    });
                }
                return false;
            });
        }
    }); // $.fn.extend({
    $(document).ready(function() {
        procApp.init();
        function __convertToNumericField(field) {
            field = field || $(field);
            if ("ontouchstart" in window || (typeof window.DocumentTouch !== "undefined" && document instanceof window.DocumentTouch)) {
                field.each(function() {
                    $(this).prop("type", "tel");
                });
            }
        }
        function checkSubmit(btnId) { //// Add/remove disabled from submit button
            if (String($(btnId).attr("data-name")) !== "" && String($(btnId).attr("data-date-read")) !== "") {
                // We trigger the click here. The button is actually hidden so user doesn't interact with it
                $(btnId).removeClass("disabled").removeAttr("disabled");
            } else {
                $(btnId).addClass("disabled").attr("disabled", true);
            }
        }
        function isLeapYear(year) {
            return ((year % 4 === 0) && (year % 100 !== 0)) || (year % 400 === 0);
        }
        function checkDate() {
            var df = $("#procDay"), mf =  $("#procMonth"), yf = $("#procYear");
            var d = df.val(), m = mf.val(), y = yf.val();
            if (!isNaN(parseInt(d))) {
                if (parseInt(d) > 0 && parseInt(d) < 10) { d = "0" + d; }
            }
            var dTest = procDateReg.test(d), mTest = (String(m) !== ""), yTest = procYearReg.test(y);
            var errorText = i18next.t("The procedure date must be valid and in required format.");
            var dgField = $("#procDateGroup"), deField = $("#procDateErrorContainer"), errorClass="error-message";

            if (dTest && mTest && yTest) {
                var isValid = tnthDates.validateDateInputFields(mf, df, yf, "procDateErrorContainer");
                if (!isValid) {
                    deField.addClass(errorClass);
                    return false;
                } else {
                    deField.removeClass(errorClass);
                }
                if (parseInt(m) === 2) { //month of February
                    if (isLeapYear(parseInt(y))) {
                        if (parseInt(d) > 29) {
                            deField.text(errorText).addClass(errorClass);
                            return false;
                        }
                    } else {
                        if (parseInt(d) > 28) {
                            dgField.addClass("has-error");
                            deField.text(errorText).addClass(errorClass);
                            return false;
                        }
                    }
                    deField.text("").removeClass(errorClass);
                    return true;
                } else {
                    deField.text("").removeClass(errorClass);
                    return true;
                }

            } else {
                return false;
            }
        }

        function setDate() {
            var isValid = checkDate();
            if (isValid) {
                var passedDate = dateFields.map(function(fn) {
                    return $("#" + fn).val();
                }).join("/");
                $("button[id^='tnthproc-submit']").attr("data-date-read", passedDate);
                var dateFormatted = tnthDates.swap_mm_dd(passedDate);
                $("button[id^='tnthproc-submit']").attr("data-date", dateFormatted);
            } else {
                $("button[id^='tnthproc-submit']").attr("data-date-read", "");
                $("button[id^='tnthproc-submit']").attr("data-date", "");
            }

            checkSubmit("button[id^='tnthproc-submit']");

        }
        // Options for datepicker - prevent future dates, no default
        $(".event-element .input-group.date").each(function() {
            $(this).datepicker({
                format: "dd/mm/yyyy",
                endDate: "0d",
                startDate: "-10y",
                autoclose: true,
                forceParse: false
            });
        }); 
        __convertToNumericField($("#procYear, #procDay"));

        // Trigger eventInput on submit button
        setTimeout(function() {
            $("#tnthproc-submit").eventInput({
                "tnthAjax": tnthAjax
            });
        }, 150);

        $("select[id^='tnthproc']").on("change", function() { // Update submit button when select changes
            $("button[id^='tnthproc-submit']")
                .attr("data-name", $(this).val())
                .attr("data-system", $(this).find("option:selected").attr("data-system"));
            checkSubmit("button[id^='tnthproc-submit']");
        });
        //datepicker field
        $("input[id^='tnthproc-value']").on("change", function() {  // Update submit button when text input changes (single option)
            $("button[id^='tnthproc-submit']")
                .attr("data-name", $(this).val())
                .attr("data-system", $(this).attr("data-system"));
            checkSubmit("button[id^='tnthproc-submit']");
        });

        dateFields.forEach(function(fn) {
            var triggerEvent = String($("#" + fn).attr("type")) === "text" ? "keyup" : "change";
            if (("ontouchstart" in window || window.DocumentTouch && document instanceof window.DocumentTouch)) {
                triggerEvent = "change";
            }
            $("#" + fn).on(triggerEvent, function() {
                setDate();
            });
        });

        $("input[id^='tnthproc-date']").on('change', function() {
            var passedDate = $(this).val(); // eg "11/20/2016"
            var dateFormatted; // Change dates to YYYY-MM-DD and make sure date is in dd/mm/yyyy format before reformat
            if (passedDate && passedDate !==  "" && /^(0[1-9]|[12][0-9]|3[01])[\/](0[1-9]|1[012])[\/]\d{4}$/.test(passedDate)) {
                $("button[id^='tnthproc-submit']").attr("data-date-read", passedDate);
                dateFormatted = tnthDates.swap_mm_dd(passedDate);
                $("button[id^='tnthproc-submit']").attr("data-date", dateFormatted);
                checkSubmit("button[id^='tnthproc-submit']"); 
            }

        });

        $("body").on("click", ".cancel-delete", function() {
            $(this).parents("div.popover").prev("a.confirm-delete").trigger("click");
        });

        $("body").on("click", ".data-delete", function() {
            $(this).closest("tr").remove();
        });
        // Need to attach delete functionality to body b/c section gets reloaded
        $("body").on("click", ".btn-delete", function() {
            var procId = $(this).parents("tr").attr("data-id");
            $(this).parents("tr").fadeOut("slow", function() {
                $(this).remove(); // Remove from list
                if ($("#eventListtnthproc tr").length === 0) { //If there's no events left, add status msg back in
                    $("body").find("#userProcedures").html("<p id='noEvents' style='margin: 0.5em 0 0 1em'><em>You haven't entered any treatments yet.</em></p>").animate({
                        opacity: 1
                    });
                }
            });
            tnthAjax.deleteProc(procId, false, false, function() { // Post delete to server
                procApp.getUserProcedures();
            });
            return false;
        });
    });
})();
