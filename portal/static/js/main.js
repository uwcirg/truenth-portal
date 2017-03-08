/*** Portal specific javascript. Topnav.js is separate and will be used across domains. **/

var userSetLang = 'en_US';// FIXME scope? defined in both tnth.js/banner and main.js
var DELAY_LOADING = false;

function equalHeightBoxes(passClass) {
    var windowsize = $(window).width();
    // Switch back to auto for small screen or to recalculate on larger
    $('.'+passClass).css("height","auto");
    if (windowsize > 768 && $('.'+passClass).length > 1) {
        var elementHeights = $('.'+passClass).map(function() {
            return $(this).height();
        }).get();
        // Math.max takes a variable number of arguments
        // `apply` is equivalent to passing each height as an argument
        var maxHeight = Math.max.apply(null, elementHeights);
        // Set each height to the max height
        $('.'+passClass).height(maxHeight);
    }
}

// Return an XHR without XHR header so  it doesn't need to be explicitly allowed with CORS
function xhr_function(){
    // Get new xhr object using default factory
    var xhr = jQuery.ajaxSettings.xhr();
    // Copy the browser's native setRequestHeader method
    var setRequestHeader = xhr.setRequestHeader;
    // Replace with a wrapper
    xhr.setRequestHeader = function(name, value) {
        // Ignore the X-Requested-With header
        if (name == 'X-Requested-With') return;
        // Otherwise call the native setRequestHeader method
        // Note: setRequestHeader requires its 'this' to be the xhr object,
        // which is what 'this' is here when executed.
        setRequestHeader.call(this, name, value);
    };
    // pass it on to jQuery
    return xhr;
}
// AJAX callback
function embed_page(data){
    $("#mainNav")
        // Embed data returned by AJAX call into container element
        .html(data).promise().done(function() {
            //for firefox? need to figure out why it doesn't show the content if not deling this call??
            if(navigator.userAgent.toLowerCase().indexOf('firefox') > -1){
                setTimeout("loader();", 300);
                //console.log("in firefox")
            } else setTimeout("loader();", 0);

        });
    // Wait until TrueNTH logo loads before displaying the navWrapper. Avoid having content flash when CSS hasn't loaded
    // $("img.tnth-topnav-wordmark").load(function(){

    // });
    // Todo: add "data-*" HTML attribute
}

function showMain() {
    $("#mainHolder").css({
                          "visibility" : "visible",
                          "-ms-filter": "progid:DXImageTransform.Microsoft.Alpha(Opacity=100)",
                          "filter": "alpha(opacity=100)",
                          "-moz-opacity": 1,
                          "-khtml-opacity": 1,
                          "opacity": 1
                        });

}

function showWrapper(hasLoader) {
    var cssProp = {"visibility":"visible", "display": "block"};
    //adding this for firefox fix
    if (!$("#tnthNavWrapper").is(":visible") || navigator.userAgent.toLowerCase().indexOf('firefox') > -1) {
        if (hasLoader) {
            $("#tnthNavWrapper").css(cssProp).promise().done(function() {
                //delay removal of loading div to prevent FOUC
                if (!DELAY_LOADING) {
                    setTimeout('$("#loadingIndicator").fadeOut();', 300);
                };
            });
        } else $("#tnthNavWrapper").css(cssProp);
    };
};

// Loading indicator that appears in UI on page loads and when saving
var loader = function(show) {
    //landing page
    if ($("#fullSizeContainer").length > 0) {
        $("#loadingIndicator").hide();
        showMain();
        return false;
    };

    if (show) {
        // $("#profileForm").addClass("loading");
        $("#loadingIndicator").show();
    } else {
        // Otherwise we'll hide it
        //issue with FOUC - need to delay showing wrapper until it is styled
        showMain();
        showWrapper(true);
        if (!DELAY_LOADING) {
            setTimeout('$("#loadingIndicator").fadeOut();', 300);
        };
    };
};

function convertToLocalTime(dateString) {
    var convertedDate = "";
    //assuming dateString is UTC date/time
    if (hasValue(dateString)) {
        var d = new Date(dateString);
        var newDate = new Date(d.getTime()+d.getTimezoneOffset()*60*1000);
        var offset = d.getTimezoneOffset() / 60;
        var hours = d.getHours();
        newDate.setHours(hours - offset);
        convertedDate = newDate.toLocaleString();
    };
    return convertedDate;
};

function convertUserDateTimeByLocaleTimeZone(dateString, timeZone, locale) {
    //firefox does not support Intl API
    //if (navigator.userAgent.toLowerCase().indexOf('firefox') > -1) return dateString;

    if (!dateString) return "";
    else {
        var errorMessage = "";
        if (!hasValue(timeZone)) timeZone = "UTC";
        if (!hasValue(locale))  locale = "en-us";
        $(".timezone-error").html("");
        $(".timezone-warning").html("");
        //locale needs to be in this format - us-en
        //month: 'numeric', day: 'numeric',
        locale = locale.replace("_", "-").toLowerCase();
        var options = {
            year: 'numeric', day: 'numeric', month: 'numeric',
            hour: 'numeric', minute: 'numeric', second: 'numeric',
            hour12: false
        };
        options.timeZone =  timeZone;
        //older browsers don't support this
        var convertedDate = dateString;
        try {
            if(/chrom(e|ium)/.test(navigator.userAgent.toLowerCase())){ //works in chrome
                convertedDate = new Date(dateString).toLocaleString(locale, options);
                if (timeZone != "UTC") $(".gmt").each(function() { $(this).hide()});
            } else {
                if (timeZone != "UTC") {
                    convertedDate = convertToLocalTime(dateString);
                    $(".timezone-warning").addClass("text-warning").html("Date/time zone conversion does not work in current browser.<br/>All date/time fields are converted to local time zone instead.");
                    $(".gmt").each(function() { $(this).hide()});
                };
            }
        } catch(e) {
            errorMessage = "Error occurred when converting timezone: " + e.message;
        };
        if (hasValue(errorMessage)) {
            $(".timezone-error").each(function() {
                $(this).addClass("text-danger").html(errorMessage);
            });
        };
        return convertedDate.replace(/\,/g, "");
    };
};

function getUserTimeZone(userId) {
    var selectVal = $("#profileTimeZone").length > 0 ? $("#profileTimeZone option:selected").val() : "";
    var userTimeZone = "";
    if (selectVal == "") {
        if (userId) {
            $.ajax ({
                type: "GET",
                url: '/api/demographics/'+userId,
                async: false
            }).done(function(data) {
                if (data) {
                    data.extension.forEach(
                        function(item, index) {
                            if (item.url === "http://hl7.org/fhir/StructureDefinition/user-timezone") {
                                userTimeZone = item.timezone;
                            };
                        });
                };

            }).fail(function() {
                userTimeZone = "UTC";
            });
        };
    } else {
        userTimeZone = selectVal;
    };

    return hasValue(userTimeZone) ? userTimeZone : "UTC";
};

function getUserLocale(userId) {
  var localeSelect = $("#locale").length > 0 ? $("#locale option:selected").val() : "";
  var locale = "";

  if (!localeSelect) {
        if (userId) {
            $.ajax ({
                    type: "GET",
                    url: '/api/demographics/'+userId,
                    async: false
            }).done(function(data) {
                if (data && data.communication) {
                    data.communication.forEach(
                        function(item, index) {
                            if (item.language) {
                                locale = item["language"]["coding"][0].code;
                                //console.log("locale: " + locale)
                            };
                    });
                };

            }).fail(function() {
                locale = "en-us";
            });
        };
   } else locale = localeSelect;

   //console.log("locale? " + locale)
   return locale ? locale : "en-us";
};

var SNOMED_SYS_URL = "http://snomed.info/sct", CLINICAL_SYS_URL = "http://us.truenth.org/clinical-codes";
var CANCER_TREATMENT_CODE = "118877007", NONE_TREATMENT_CODE = "999";
var CONSENT_ENUM = {
    "consented": {
        "staff_editable": true,
        "include_in_reports": true,
        "send_reminders": true
    },
     "suspended": {
        "staff_editable": true,
        "include_in_reports": true,
        "send_reminders": false
    },
    "purged": {
        "staff_editable": false,
        "include_in_reports": false,
        "send_reminders": false
    }
};


var fillContent = {
    "clinical": function(data) {
        $.each(data.entry, function(i,val){
            var clinicalItem = val.content.code.coding[0].display;
            if (clinicalItem == "PCa diagnosis") {
                clinicalItem = "pca_diag";
            } else if (clinicalItem == "PCa localized diagnosis") {
                clinicalItem = "pca_localized";
            }
            var ci = $('div[data-topic="'+clinicalItem+'"]');
            if (ci.length > 0) ci.fadeIn().next().fadeIn();
            var clinicalValue = val.content.valueQuantity.value;
            var $radios = $('input:radio[name="'+clinicalItem+'"]');
            if ($radios.length > 0) {
                if($radios.is(':checked') === false) {
                    $radios.filter('[value='+clinicalValue+']').prop('checked', true);
                }
            };
        })
    },
    "demo": function(data) {
        //console.log("in demo");
        //console.log(data)

        $('#firstname').val(data.name.given);
        $('#lastname').val(data.name.family);
        if (data.birthDate) {
            var bdArray = data.birthDate.split("-");
            $("#birthday").val(data.birthDate);
            $("#year").val(bdArray[0]);
            $("#month").val(bdArray[1]);
            $("#date").val(bdArray[2]);
            // If there's already a birthday, then we should show the patientQ if this is a patient (determined with roles)
            //$("#patBiopsy").fadeIn();
        };
        if (data.deceasedDateTime) {
            if(hasValue(data.deceasedDateTime)) {
                var dArray = (data.deceasedDateTime.split("T"))[0].split("-");
                $("#deathYear").val(dArray[0]);
                $("#deathMonth").val(dArray[1]);
                $("#deathDay").val(dArray[2]);
                $("#deathDate").val(dArray[0] + "-" + dArray[1] + "-" + dArray[2]);
                $("#boolDeath").prop("checked", true);
            } else {
                $("#deathYear").val("");
                $("#deathMonth").val("");
                $("#deathDay").val("");
                $("#deathDate").val("");
                $("#boolDeath").prop("checked", false);
            };
        }

        if (data.deceasedBoolean) {
            if (String(data.deceasedBoolean).toLowerCase() == "true") {
                $("#boolDeath").prop("checked", true);
            } else $("#boolDeath").prop("checked", false);
        };
        // TODO - add email and phone for profile page use
        // Only on profile page
        this.ethnicity(data);
        // Get Races
        this.race(data);
        this.indigenous(data);
        this.orgs(data);
    },
    "name": function(data){
        if (data && data.name) {
            $('#firstname').val(data.name.given);
            $('#lastname').val(data.name.family);
        };
    },
    "dob": function(data) {
        if (data && data.birthDate) {
            var bdArray = data.birthDate.split("-");
            $("#birthday").val(data.birthDate);
            $("#year").val(bdArray[0]);
            $("#month").val(bdArray[1]);
            $("#date").val(bdArray[2]);
            // If there's already a birthday, then we should show the patientQ if this is a patient (determined with roles)
            if ($("#patBiopsy").length > 0) $("#patBiopsy").fadeIn();
        };
    },
    "ethnicity": function(data) {
        data.extension.forEach(function(item, index) {
            if (item.url === "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity") {
                //console.log(item)
                item.valueCodeableConcept.coding.forEach(function(val){
                    $("#userEthnicity input:radio[value="+val.code+"]").prop('checked', true);
                    // Way to handle non-standard codes - output but hide, for submitting on update
                    if ($("#userEthnicity input:radio[value="+val.code+"]").length == 0) {
                        if (val.code !== "undefined") $("#userEthnicity").append("<input class='tnth-hide' type='checkbox' checked name='ethnicity' value='"+val.code+"' data-label='"+val.display+"' />");
                    }
                });
            };
        });
    },
    "race": function(data) {
        // Get Races
        data.extension.forEach(function(item, index) {
            if (item.url === "http://hl7.org/fhir/StructureDefinition/us-core-race") {
                item.valueCodeableConcept.coding.forEach(function(val){
                    //console.log(val)
                    $("#userRace input:checkbox[value="+val.code+"]").prop('checked', true);
                    // Way to handle non-standard codes
                    if ($("#userRace input:checkbox[value="+val.code+"]").length == 0) {
                        // If there is any non-standard, then check the "other" in the UI
                        $("#userRace input:checkbox[value=2131-1]").prop('checked', true);
                        // Add hidden list of non-standard for form submission
                       if (val.code !== "undefined") $("#userRace").append("<input class='tnth-hide' type='checkbox' checked name='race' value='"+val.code+"' data-label='"+val.display+"' />");
                        //$("#raceOtherVal").fadeToggle();
                    }
                });
            };
        });
    },
    "indigenous": function(data) {
        data.extension.forEach(function(item, index) {
            if (item.url === "http://us.truenth.org/fhir/StructureDefinition/AU-NHHD-METeOR-id-291036") {
                item.valueCodeableConcept.coding.forEach(function(val){
                    //console.log(val)
                    $("#userIndigenousStatus input[type='radio'][value="+val.code+"]").prop('checked', true);

                });
            };
        });
    },
    "orgs": function(data) {
        $("#userOrgs input[name='organization']").each(function() {
            $(this).prop("checked", false);
        });

        $.each(data.careProvider,function(i,val){
            var orgID = val.reference.split("/").pop();
            if (orgID == "0") $("#userOrgs #noOrgs").prop("checked", true);
            else $("body").find("#userOrgs input.clinic:checkbox[value="+orgID+"]").prop('checked', true);
        });

        // If there's a pre-selected clinic set in session, then fill it in here (for initial_queries)
        if ((typeof preselectClinic != "undefined") && hasValue(preselectClinic)) {
            $("body").find("#userOrgs input.clinic[value="+preselectClinic+"]").prop('checked', true);
        };

        if ($('#userOrgs input.clinic:checked').size()) {
            $("#terms").fadeIn();
        }
    },
    "subjectId": function(data) {
        if (data.identifier) {
            (data.identifier).forEach(function(item) {
                if (item.system == "http://us.truenth.org/identity-codes/external-study-id") {
                    if (hasValue(item.value)) $("#profileStudyId").val(item.value);
                };
            });
        };
    },
    "consentList" : function(data, userId, errorMessage, errorCode) {
        if (data && data["consent_agreements"] && data["consent_agreements"].length > 0) {
            var dataArray = data["consent_agreements"].sort(function(a,b){
                return new Date(b.signed) - new Date(a.signed);
            });
            var orgs = {};
            var existingOrgs = {};
            var hasConsent = false;
            var isAdmin = typeof _isAdmin != "undefined" && _isAdmin ? true: false;
            var userTimeZone = getUserTimeZone(userId);
            var userLocale = getUserLocale(userId);
            var ctop = (typeof CONSENT_WITH_TOP_LEVEL_ORG != "undefined") && CONSENT_WITH_TOP_LEVEL_ORG;

            $.ajax ({
                type: "GET",
                url: '/api/organization',
                async: false,
                timeout: 20000
            }).done(function(data) {
                if (data) {
                    data.entry.forEach(function(entry) {
                        //console.log(entry["id"] +  " " + entry["name"] + " partOf: " + entry["partOf"])
                        var oi = entry["id"];
                        if (hasValue(oi)  && (parseInt(oi) != 0)) {
                            orgs[oi] = {
                                "_name" : entry["name"],
                                "partOf": entry["partOf"] ? (entry["partOf"]["reference"]).split("/")[2] : null
                            };
                        };
                    });
                };
            });

            var editable = (typeof consentEditable != "undefined" && consentEditable == true) ? true : false;
            var content = "<table class='table-bordered table-hover table-condensed table-responsive' style='width: 100%; max-width:100%'>";
            ['Organization', 'Consent Status', '<span class="agreement">Agreement</span>', 'Consented Date <span class="gmt">(GMT)</span>'].forEach(function (title, index) {
                if (title != "n/a") content += "<TH class='consentlist-header'>" + title + "</TH>";
            });

            var hasContent = false;

            //recursively get the top level org name
            function getOrgName (_orgId) {
                if (!(orgs[_orgId].partOf)) {
                    return orgs[_orgId]._name;
                }
                else {
                    return getOrgName(orgs[_orgId].partOf);
                };
            };

            //console.log(orgs)

            dataArray.forEach(function(item, index) {
                if (!(existingOrgs[item.organization_id]) && !(/null/.test(item.agreement_url))) {
                    hasContent = true;
                    var orgName = "";
                    var orgId = item.organization_id;
                    if (!ctop) {
                        try {
                            orgName = getOrgName(orgId);
                        } catch(e) {
                            orgName = orgs[orgId]._name;
                        };
                    } else orgName = orgs[orgId]._name;

                    //orgs[item.organization_id] ? orgs[item.organization_id]._name: item.organization_id;
                    var expired = tnthDates.getDateDiff(item.expires);
                    var consentStatus = item.deleted ? "deleted" : (expired > 0 ? "expired": "active");
                    var deleteDate = item.deleted ? item.deleted["lastUpdated"]: "";
                    var sDisplay = "", cflag = "";
                    var se = item.staff_editable, sr = item.send_reminders, ir = item.include_in_reports, cflag = "";
                    var signedDate = convertUserDateTimeByLocaleTimeZone(item.signed, userTimeZone, userLocale);
                    var expiresDate = convertUserDateTimeByLocaleTimeZone(item.expires, userTimeZone, userLocale);


                    switch(consentStatus) {
                        case "deleted":
                            sDisplay = "<span class='text-danger'>&#10007;</span><br/><span class='text-danger' style='font-size: 0.9em'>(deleted on " + deleteDate.replace("T", " ") + " GMT)</span>";
                            break;
                        case "expired":
                            sDisplay = "<span class='text-warning'>&#10007; <br><span>(expired)</span>"
                            break;
                        case "active":
                            if (se && sr && ir) {
                                    sDisplay = "<span class='text-success small-text'>Consented / Enrolled</span>";
                                    cflag = "consented";
                            } else if (se && ir && !sr) {
                                    sDisplay = "<span class='text-warning small-text'>Suspend Data Collection and Reports</span>";
                                    cflag = "suspended";
                            } else if (!se && !ir && !sr) {
                                    sDisplay = "<span class='text-danger small-text'>Purged/Removed</span>";
                                    cflag = "purged";
                            } else {
                                //backward compatible?
                                sDisplay = "<span class='text-success small-text'>Consented / Enrolled</span>";
                                cflag = "consented";
                            };
                            break;
                    };
                    var modalContent = "";

                    if (editable && consentStatus == "active") {
                        modalContent += '<div class="modal fade" id="consent' + index + 'Modal" tabindex="-1" role="dialog" aria-labelledby="consent' + index + 'ModalLabel">'
                            + '<div class="modal-dialog" role="document">'
                            + '<div class="modal-content">'
                            + '<div class="modal-header">'
                            + '<button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>'
                            + '<h5 class="modal-title">Consent Status Editor</h5>'
                            + '</div>'
                            + '<div class="modal-body" style="padding: 0 2em">'
                            + '<br/><h4 style="margin-bottom: 1em"><em>Modify</em> the consent status for this user to: </h4>'
                            + '<div style="font-size:0.95em; margin-left:1em">'
                            + '<div class="radio"><label><input class="radio_consent_input" name="radio_consent_' + index + '" type="radio" modalId="consent' + index + 'Modal" value="consented" orgId="' + item.organization_id + '" agreementUrl="' + String(item.agreement_url).trim() + '" userId="' + userId + '" ' +  (cflag == "consented"?"checked": "") + '>Consented / Enrolled</input></label></div>'
                            + '<div class="radio"><label class="text-warning"><input class="radio_consent_input" name="radio_consent_' + index + '" type="radio" modalId="consent' + index + 'Modal" value="suspended" orgId="' + item.organization_id + '" agreementUrl="' + String(item.agreement_url).trim() + '" userId="' + userId + '" ' +  (cflag == "suspended"?"checked": "") + '>Suspend Data Collection and Report Historic Data</input></label></div>'
                            + (isAdmin ? ('<div class="radio"><label class="text-danger"><input class="radio_consent_input" name="radio_consent_' + index + '" type="radio" modalId="consent' + index + 'Modal" value="purged" orgId="' + item.organization_id + '" agreementUrl="' + String(item.agreement_url).trim() + '" userId="' + userId + '" ' + (cflag == "purged"?"checked": "") +'>Purged/remove consent(s) associated with this organization</input></label></div>') : "")
                            + '</div><br/><br/>'
                            + '</div>'
                            + '<div class="modal-footer">'
                            + '<button type="button" class="btn btn-default" data-dismiss="modal" style="font-size:0.9em">Close</button>'
                            + '</div>'
                            + '</div></div></div>';

                    };
                    content += "<tr>";

                    [
                        {
                            content: (orgName != "" && orgName != undefined? orgName : item.organization_id)
                        },
                        {
                            content: sDisplay + (editable && consentStatus == "active"? '&nbsp;&nbsp;<a data-toggle="modal" data-target="#consent' + index + 'Modal" ><span class="glyphicon glyphicon-pencil" aria-hidden="true" style="cursor:pointer; color: #000"></span></a>' + modalContent: ""),
                            "_class": "indent"
                        },
                        {
                            content: "<span class='agreement'><a href='" + item.agreement_url + "' target='_blank'><em>View</em></a></span>"

                        },
                        {
                            content: (signedDate).replace("T", " ")
                        }
                    ].forEach(function(cell) {
                        if (cell.content != "n/a") content += "<td class='consentlist-cell" + (cell._class? (" " + cell._class): "") + "' >" + cell.content + "</td>";
                    });
                    content += "</tr>";
                    existingOrgs[item.organization_id] = true;
                };

            });
            content += "</table>";

            if (hasContent) {
                $("#profileConsentList").html(content);
                if (!ctop) $("#profileConsentList .agreement").each(function() {
                    $(this).parent().hide();
                });
                if ($(".timezone-error").text() == "" && (userTimeZone.toUpperCase() != "UTC")) $("#profileConsentList .gmt").each(function() {
                    $(this).hide();
                });
            } else $("#profileConsentList").html("<span class='text-muted'>No Consent Record Found</span>");

            if (editable) {
                $("input[class='radio_consent_input']").each(function() {
                    $(this).on("click", function() {
                        var o = CONSENT_ENUM[$(this).val()];
                        if (o) {
                            o.org = $(this).attr("orgId");
                            o.agreementUrl = $(this).attr("agreementUrl");
                        };
                        if ($(this).val() == "purged") tnthAjax.deleteConsent($(this).attr("userId"), {org: $(this).attr("orgId")});
                        else  tnthAjax.setConsent(userId, o, $(this).val());
                        $("#" + $(this).attr("modalId")).modal('hide');
                        if (typeof reloadConsentList != "undefined") reloadConsentList();
                    });
                });
            };

        } else {
            $("#profileConsentList").html(errorMessage ? ("<p class='text-danger' style='font-size:0.9em'>" + errorMessage + "</p>") : "<p class='text-muted'>No consent found for this user.</p>");
            if (parseInt(errorCode) == 401) {
                var msg = " You do not have permission to edit this patient record.";
                $("#profileConsentList").html("<p class='text-danger'>" + msg + "</p>");
            };
        };
        $("#profileConsentList").animate({opacity: 1});
    },
    "treatment": function(data) {
        var treatmentCode = tnthAjax.hasTreatment(data);
        if (treatmentCode) {
            if (treatmentCode == CANCER_TREATMENT_CODE) {
                $("#tx_yes").prop("checked", true);
            } else {
                $("#tx_no").prop("checked", true);
            };
        };
    },
    "proceduresContent": function(data,newEntry) {
        if (data.entry.length == 0) {
            $("body").find("#userProcedures").html("<p id='noEvents' style='margin: 0.5em 0 0 1em'><em>You haven't entered any management option yet.</em></p>").animate({opacity: 1});
            return false;
        }

        // sort from newest to oldest
        data.entry.sort(function(a,b){
            return new Date(b.resource.performedDateTime) - new Date(a.resource.performedDateTime);
        });
        var proceduresHtml = '<table  class="table-responsive" width="100%" id="eventListtnthproc" cellspacing="4" cellpadding="6">';

        // If we're adding a procedure in-page, then identify the highestId (most recent) so we can put "added" icon
        var highestId = 0;
        $.each(data.entry,function(i,val){
            var procID = val.resource.id, code = val.resource.code.coding[0].code;        
            var displayText = val.resource.code.coding[0].display;
            var performedDateTime = val.resource.performedDateTime;
            var performedDate = new Date(String(performedDateTime).replace(/-/g,"/").substring(0, performedDateTime.indexOf('T')));
            var cPerformDate = performedDate.toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'});
            //console.log("date: " + performedDateTime + " cdate: " + performedDate);
            var deleteInvocation = '';
            var creator = val.resource.meta.by.reference;
            creator = creator.match(/\d+/)[0];// just the user ID, not eg "api/patient/46";
            if (creator == currentUserId) {
                creator = "you";
                deleteInvocation = "  <a data-toggle='popover' class='btn btn-default btn-xs confirm-delete' style='border-radius:4px; font-size:0.9em; padding: 0.2em 0.6em; color:#777' data-content='Are you sure you want to delete this treatment?<br /><br /><a href=\"#\" class=\"btn-delete btn btn-tnth-primary\">Yes</a> &nbsp;&nbsp;&nbsp; <a class=\"btn btn-default cancel-delete\">No</a>' rel='popover'><i class='fa fa-times'></i> Delete</span>";
            }
            else if (creator == subjectId) {
                creator = "this patient";
            }
            else creator = "staff member <span class='creator'>" + creator + "</span>";
            var dtEdited = val.resource.meta.lastUpdated;
            dateEdited = new Date(dtEdited);
            proceduresHtml += "<tr " + ((code == CANCER_TREATMENT_CODE || code == NONE_TREATMENT_CODE) ? "class='tnth-hide'" : "") + " data-id='" + procID + "' data-code='" + code + "' style='font-family: Georgia serif; font-size:1.1em'><td width='1%' valign='top'>&#9679;</td><td class='col-md-8 col-xs-9'>" + (cPerformDate?cPerformDate:performedDate) + "&nbsp;--&nbsp;" + displayText + "&nbsp;<em>(data entered by " + creator + " on " + dateEdited.toLocaleDateString('en-GB', {day: 'numeric', month: 'short', year: 'numeric'}) + ")</em></td><td class='col-md-4 col-xs-3 lastCell text-left'>&nbsp;" + deleteInvocation + "</td></tr>";
            if (procID > highestId) {
                highestId = procID;
            };
        });
        proceduresHtml += '</table>';

        $("body").find("#userProcedures").html(proceduresHtml).animate({opacity: 1});

        var dataRows = $("#userProcedures tr[data-id]");
        if (dataRows.length == $("#userProcedures tr[class='tnth-hide']").length) $(dataRows.get(0)).removeClass("tnth-hide");

        /******* comment this part out for now, getting unauthorized error to access other user's demographics, which makes sense
        $("#userProcedures .creator").each(function() {
            var uid = $.trim($(this).text()), self=this, userIdentity="";
            if (hasValue(uid)) {
                $.ajax ({
                    type: "GET",
                    url: '/api/demographics/'+uid
                }).done(function(data) {
                    console.log(data)
                    if (data) {
                        if (data.name) {
                            userIdentity = (hasValue(data.name.given) ? data.name.given: "") + " " + (hasValue(data.name.family) ? data.name.family : "");
                        }
                        if (!hasValue($.trim(userIdentity))) {
                            if (data.telecom) {
                                (data.telecom).forEach(function(item) {
                                    if (item.system == "email") userIdentity = item.value;
                                });
                            };
                        };
                    };
                    if (hasValue(userIdentity)) $(self).text(userIdentity);
                }).fail(function() {
                });
            };
        });*****/
        // If newEntry, then add icon to what we just added
        if (newEntry) {
            $("#eventListtnthproc").find("tr[data-id='" + highestId + "'] td.lastCell").append("&nbsp; <small class='text-success'><i class='fa fa-check-square-o'></i> <em>Added!</em></small>");
        }
        $('[data-toggle="popover"]').popover({
            trigger: 'click',
            placement: 'top',
            html: true
        });
    },
    "timezone": function(data) {
        data.extension.forEach(function(item, index) {
            if (item.url === "http://hl7.org/fhir/StructureDefinition/user-timezone") {
                $("#profileTimeZone option").each(function() {
                    if ($.trim($(this).val()) == $.trim(item.timezone)) {
                        $(this).prop("selected", true);
                    };
                });
            };
        });
    },
    "roleList": function(data) {
        data.roles.forEach(function(role) {
            $("#rolesGroup").append("<div class='checkbox'><label><input type='checkbox' name='user_type' value='" + role.name + "' save-container-id='rolesGroup'>" + role.name.replace(/\_/g, " ").replace(/\b[a-z]/g,function(f){return f.toUpperCase();}) + "</label></div>");
        });
    },
    "roles": function(data,isProfile) {
        $.each(data.roles, function(i,val){
            var userRole = val.name;
            // Handle profile differently than initial_queries
            if (isProfile) {
                $.each(data.roles,function(i,val){
                    $("#rolesGroup input:checkbox[value="+val.name+"]").prop('checked', true);
                });
            } else {
                var $radios = $('input[name=user_type]');
                if($radios.is(':checked') === false) {
                    $radios.filter('[value='+userRole+']').prop('checked', true);
                };
            }
        });
    }
};

var assembleContent = {
    "demo": function(userId,onProfile, targetField, sync) {

        var demoArray = {};
        demoArray["resourceType"] = "Patient";

        var fname = $("input[name=firstname]").val(), lname = $("input[name=lastname]").val();

        demoArray["name"] = {
            "given": $.trim(fname),
            "family": $.trim(lname)
        };


        var bdFieldVal = $("input[name=birthDate]").val();
        if (bdFieldVal != "") demoArray["birthDate"] = bdFieldVal;

        $.each($("#userOrgs input"),function(i,v){
            if ($(this).attr("data-parent-id")) {
                if ($(this).attr("type") == "checkbox" || $(this).attr("type") == "radio") $("#userOrgs input[value="+$(this).attr("data-parent-id")+"]").prop('checked', false);
            };
        });

        if ($("#userOrgs input[name='organization']").length > 0) {
            var orgIDs;
            orgIDs = $("#userOrgs input[name='organization']").map(function(){
                    if ($(this).prop("checked")) return { reference: "api/organization/"+$(this).val() };
            }).get();

            if (orgIDs) {
                if (orgIDs.length > 0) {
                    demoArray["careProvider"] = orgIDs;
                } else {
                    //don't update org to none if at the initial queries page
                    if ($("#aboutForm").length == 0) demoArray["careProvider"] = [{reference: "api/organization/" + 0}];
                };
            };

        };

        if (hasValue($("#deathDate").val())) {
            demoArray["deceasedDateTime"] = $("#deathDate").val();
        };

        if (!hasValue($("#deathDate").val())) {
            if ($("#boolDeath").length > 0) {
                if ($("#boolDeath").prop("checked")) {
                    demoArray["deceasedBoolean"] = true;
                } else demoArray["deceasedBoolean"] = false;
            };
        };

        if (onProfile) {

            // Grab profile field values - looks for regular and hidden, can be checkbox or radio
            var e =  $("#userEthnicity"), r = $("#userRace"), i = $("#userIndigenousStatus"), tz = $("#profileTimeZone");
            var ethnicityIDs, raceIDs, indigenousIDs, tzID;

            demoArray["extension"] = [];


            if (e.length > 0) {
                ethnicityIDs = $("#userEthnicity input:checked").map(function(){
                    return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Ethnicity" };
                }).get();

                if (ethnicityIDs) {
                    demoArray["extension"].push(
                        {   "url": "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity",
                            "valueCodeableConcept": {
                                "coding": ethnicityIDs
                            }
                        }
                    );
                };
            };
            // Look for race checkboxes, can be hidden
            if (r.length > 0 ) {
                raceIDs = $("#userRace input:checkbox:checked").map(function(){
                    return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Race" };
                }).get();
                if (raceIDs) {
                    demoArray["extension"].push(
                        {   "url": "http://hl7.org/fhir/StructureDefinition/us-core-race",
                            "valueCodeableConcept": {
                                "coding": raceIDs
                            }
                        }
                    );

                };
            };

            if (i.length > 0) {
                indigenousIDs = $("#userIndigenousStatus input[type='radio']:checked").map(function() {
                    return { code: $(this).val(), system: "http://us.truenth.org/fhir/valueset/AU-NHHD-METeOR-id-291036" };
                }).get();
                if (indigenousIDs) {
                    demoArray["extension"].push(
                        {   "url": "http://us.truenth.org/fhir/StructureDefinition/AU-NHHD-METeOR-id-291036",
                             "valueCodeableConcept": {
                                 "coding": indigenousIDs
                             }
                         }
                    )
                };
            };

            if ($("#locale").length > 0 && $("#locale").find("option:selected").length > 0) {
                demoArray["communication"] = [
                    {"language": {
                        "coding": [
                            {   "code": $("#locale").find("option:selected").val(),
                                "display": $("#locale").find("option:selected").text(),
                                "system": "urn:ietf:bcp:47"
                            }
                        ]
                    }}
                ];
            };

            if (tz.length > 0) {
                tzID = $("#profileTimeZone option:selected").val();
                if (tzID) {
                    demoArray["extension"].push(
                        {
                            timezone: tzID,
                            url: "http://hl7.org/fhir/StructureDefinition/user-timezone"
                        }
                    );
                };
            };


            var studyId = $("#profileStudyId").val();
            if (hasValue(studyId)) {
                studyId = $.trim(studyId);
                var identifiers = null;
                //get current identifier(s)
                $.ajax ({
                    type: "GET",
                    url: '/api/demographics/'+userId,
                    async: false
                }).done(function(data) {
                    if (data && data.identifier) {
                        identifiers = [];
                        (data.identifier).forEach(function(identifier) {
                            if (identifier.system != "http://us.truenth.org/identity-codes/external-study-id") identifiers.push(identifier);
                        });
                    };
                }).fail(function() {
                   // console.log("Problem retrieving data from server.");
                });

                var studyIdObj = {
                    system: "http://us.truenth.org/identity-codes/external-study-id",
                    use: "secondary",
                    value: studyId
                };

                if (identifiers) {
                    identifiers.push(studyIdObj);
                } else {
                    identifiers = [studyIdObj];
                };
                demoArray["identifier"] = identifiers;
            };


            demoArray["gender"] = $("input[name=sex]:checked").val();

            demoArray["telecom"] = [];

            var emailVal = $("input[name=email]").val();
            if ($.trim(emailVal) != "") {
                demoArray["telecom"].push({ "system": "email", "value": $.trim(emailVal) });
            };
            demoArray["telecom"].push({ "system": "phone", "value": $.trim($("input[name=phone]").val()) });
           //console.log("demoArray", demoArray);
        };
        tnthAjax.putDemo(userId,demoArray, targetField, sync);

    },
    "name": function(userId) {

        var firstName = $("input[name=firstname]").val();
        var lastName = $("input[name=lastname]").val();
        if (firstName != "" && lastName != "") {
            var demoArray = {};
            demoArray["resourceType"] = "Patient";
            demoArray["name"] = {
                "given": $("input[name=firstname]").val(),
                "family": $("input[name=lastname]").val()
            };
            tnthAjax.putDemo(userId,demoArray);
        };

    },
    "dob": function(userId) {
        var demoArray = {};
        var birthday = $("input[name='birthDate']").val();
        var month = $("#month").find("option:selected").val();
        var day = $("input[name='birthdayDate']").val();
        var year = $("input[name='birthdayYear']").val();
        var birthDate = "";

        if (birthday == "") {
            if (month != "" && day != "" && year != "") {
                birthDate = year + "-" + month + "-" + day;
            };
        };
        if (birthday  != "" || birthDate != "") {
            demoArray["resourceType"] = "Patient";
            demoArray["birthDate"] = (birthday != "" ? birthday: birthDate);
            tnthAjax.putDemo(userId,demoArray);
        }
    },
    "orgs": function(userId) {

        var orgIDs = $("#userOrgs input[name='organization']:checked").map(function(){
            return { reference: "api/organization/"+$(this).val() };
        }).get();

        //console.log("org ids" + orgIDs)

        if (typeof orgIDs === 'undefined'){
            orgIDs = [0]  // special value for `none of the above`
        };


        var demoArray = {};
        demoArray["resourceType"] = "Patient";
        demoArray["careProvider"] = orgIDs;
        //console.log(demoArray)
        tnthAjax.putDemo(userId, demoArray);
    },
    "coreData": function(userId) {
        var demoArray = {};
        demoArray["resourceType"] = "Patient";
        demoArray["extension"] = [];
        if ($("#userEthnicity").length > 0) {
            var ethnicityIDs = $("#userEthnicity input:checked").map(function(){
                return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Ethnicity" };
            }).get();
            demoArray["extension"].push(
                { "url": "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity",
                    "valueCodeableConcept": {
                        "coding": ethnicityIDs
                    }
                }
            );
        }
        if ($("#userRace").length > 0) {
            var raceIDs = $("#userRace input:checkbox:checked").map(function(){
                return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Race" };
            }).get();
            demoArray["extension"].push(
                { "url": "http://hl7.org/fhir/StructureDefinition/us-core-race",
                    "valueCodeableConcept": {
                        "coding": raceIDs
                    }
                }
            );
        }
        tnthAjax.putDemo(userId,demoArray);
    }
};

var OrgObj = function(orgId, orgName, parentOrg) {
    this.id = orgId;
    this.name = orgName;
    this.children = [];
    this.parentOrgId = parentOrg;
    this.isTopLevel = false;
};

var OrgTool = function() {

    var TOP_LEVEL_ORGS = [];
    var orgsList = {};

    this.inArray = function (val, array) {
        if (val && array) {
            for (var i = 0; i < array.length; i++) {
                if (array[i] == val) return true;
            };
        };
        return false;
    };

    this.getTopLevelOrgs = function() {
        return TOP_LEVEL_ORGS;
    }

    this.getOrgsList = function() {
        return orgsList;
    };

    this.filterOrgs = function(leafOrgs) {
        //console.log(leafOrgs)
        if (!leafOrgs) return false;
        var self = this;

        $("input[name='organization']").each(function() {
            if (! self.inArray($(this).val(), leafOrgs)) {
                $(this).hide();
                if (orgsList[$(this).val()] && orgsList[$(this).val()].children.length == 0) $(this).closest("label").hide();
            };
        });

        var topList = self.getTopLevelOrgs();

        topList.forEach(function(orgId) {
            var allChildrenHidden = true;
            $(".org-container[data-parent-id='" + orgId + "']").each(function() {
                var subOrgs = $(this).find(".org-container");
                if (subOrgs.length > 0) {
                    var allSubOrgsHidden = true;
                    subOrgs.each(function() {
                         var isVisible = false;
                         $(this).find("input[name='organization']").each(function() {
                             if ($(this).is(":visible") || $(this).css("display") != "none") {
                                isVisible = true;
                                allChildrenHidden = false;
                             };
                         });

                        if (!isVisible) {
                            $(this).hide();
                        } else allSubOrgsHidden = false;

                    });

                    if (allSubOrgsHidden) $(this).children("label").hide();

                } else {
                    var ip = $(this).find("input[name='organization']");
                    if (ip.length > 0) {
                        ip.each(function() {
                            if ($(this).is(":visible") || $(this).css("display") != "none") allChildrenHidden = false;
                        });
                    };
                };
            });
            if (allChildrenHidden) {
                $("#fillOrgs").find("legend[orgid='" + orgId + "']").hide();
            };

        });
    };

    this.findOrg = function(entry, orgId) {
        var org;
        if (entry && orgId) {
            entry.forEach(function(item) {
                if (!org) {
                    if (item.id == orgId) org = item;
                };
            });
        };
        return org;
    };
    this.getTopLevelOrgs = function() {
        if (TOP_LEVEL_ORGS.length == 0) {
            var topOrgs = $("#fillOrgs").find(input[name='organization'][parent_org='true']);
            if (topOrgs.length > 0) {
                topOrgs.each(function() {
                    TOP_LEVEL_ORGS.push[$(this).val()];
                });
            };
        };
        return TOP_LEVEL_ORGS;
    };

    this.populateOrgsList = function(items) {
        if (!items) return false;
        var entry = items, self = this, parentId;
        items.forEach(function(item) {
            if (item.partOf) {
                parentId = item.partOf.reference.split("/").pop();
                if (!orgsList[parentId]) {
                    var o = self.findOrg(entry, parentId);
                    orgsList[parentId] = new OrgObj(o.id, o.name);
                };
                orgsList[parentId].children.push(new OrgObj(item.id, item.name, parentId));
                if (orgsList[item.id]) orgsList[item.id].parentOrgId = parentId;
                else orgsList[item.id] = new OrgObj(item.id, item.name, parentId);
            } else {
                if (!orgsList[item.id]) orgsList[item.id] = new OrgObj(item.id, item.name);
                if (item.id != 0) {
                    orgsList[item.id].isTopLevel = true;
                    TOP_LEVEL_ORGS.push(item.id);
                };
            };
        });
        items.forEach(function(item) {
            if (item.partOf) {
                parentId = item.partOf.reference.split("/").pop();
                if (orgsList[item.id]) orgsList[item.id].parentOrgId = parentId;
            };
        });
        //console.log(orgsList)
        return orgsList;
    };

    this.populateUI = function() {
        var parentOrgsCt = 0, topLevelOrgs = this.getTopLevelOrgs();
        for (org in orgsList) {
            if (orgsList[org].isTopLevel && (orgsList[org].children.length > 0)) {
                $("#fillOrgs").append("<legend orgId='" + org + "'>"+orgsList[org].name+"</legend><input class='tnth-hide' type='checkbox' name='organization' parent_org=\"true\" org_name=\"" + orgsList[org].name + "\" id='" + orgsList[org].id + "_org' value='"+orgsList[org].id+"' />");
                parentOrgsCt++;
            }
            // Fill in each child clinic
            if (orgsList[org].children.length > 0) {
                var childClinic = "";
                orgsList[org].children.forEach(function(item, index) {
                    var _parentOrgId = item.parentOrgId;
                    var _parentOrg = orgsList[_parentOrgId];
                    var _isTopLevel = _parentOrg ? _parentOrg.isTopLevel : false;
                    childClinic = '<div id="' + item.id + '_container" ' + (_isTopLevel ? (' data-parent-id="'+_parentOrgId+'"  data-parent-name="' + _parentOrg.name + '" ') : "") +' class="indent org-container">'

                    if (orgsList[item.id].children.length > 0) {
                        childClinic += '<label id="org-label-' + item.id + '" class="org-label ' + (orgsList[item.parentOrgId].isTopLevel ? "text-muted": "text-muter") + '">' +
                        '<input class="clinic" type="checkbox" name="organization" id="' +  item.id + '_org" value="'+
                        item.id +'"  ' +  (_isTopLevel ? (' data-parent-id="'+_parentOrgId+'"  data-parent-name="' + _parentOrg.name + '" ') : "") + '/>'+
                        item.name +
                        '</label>';

                     } else {
                        childClinic += '<label id="org-label-' + item.id + '" class="org-label">' +
                        '<input class="clinic" type="checkbox" name="organization" id="' +  item.id + '_org" value="'+
                        item.id +'"  ' +  (_isTopLevel ? (' data-parent-id="'+_parentOrgId+'"  data-parent-name="' + _parentOrg.name + '" ') : "") + '/>'+
                        item.name +
                        '</label>';
                    };

                    childClinic += '</div>';

                    if ($("#" + _parentOrgId + "_container").length > 0) $("#" + _parentOrgId + "_container").append(childClinic);
                    else $("#fillOrgs").append(childClinic);

                });
            };

            if (parentOrgsCt > 0 && orgsList[org].isTopLevel) $("#fillOrgs").append("<span class='divider'>&nbsp;</span>");
        };
    };
};

var OT = new OrgTool();

var tnthAjax = {
    "getOrgs": function(userId, noOverride, sync, callback) {
        loader(true);
        var self = this;
        $.ajax ({
            type: "GET",
            url: '/api/organization',
            async: sync? false : true
        }).done(function(data) {

            $("#fillOrgs").attr("userId", userId);
            $(".get-orgs-error").remove();

            OT.populateOrgsList(data.entry);
            OT.populateUI();
            tnthAjax.getDemo(userId, noOverride, sync, callback);
            if ((typeof preselectClinic != "undefined") && hasValue(preselectClinic)) {
                var ob = $("body").find("#userOrgs input.clinic[value="+preselectClinic+"]");
                ob.prop('checked', true);
                tnthAjax.handleConsent(ob);
            };

            $("#userOrgs input[name='organization']").each(function() {
                $(this).on("click", function() {

                    var userId = $("#fillOrgs").attr("userId");
                    var parentOrg = $(this).attr("data-parent-id");

                    if ($(this).prop("checked")){
                        if ($(this).attr("id") !== "noOrgs") {
                            //console.log("set no org here")
                            $("#noOrgs").prop('checked',false);

                        } else {
                            $("#userOrgs input[name='organization']").each(function() {
                                //console.log("in id: " + $(this).attr("id"))
                               if ($(this).attr("id") !== "noOrgs") {
                                    $(this).prop('checked',false);
                               } else {
                                    if (typeof sessionStorage != "undefined" && sessionStorage.getItem("noOrgModalViewed")) sessionStorage.removeItem("noOrgModalViewed");
                               };
                            });

                        };
                    } else {
                        var isChecked = false;
                        $("#userOrgs input[name='organization']").each(function() {
                            if ($(this).prop("checked")) {
                                isChecked = true;
                            };
                        });
                        if (!isChecked) {
                            if (typeof sessionStorage != "undefined" && sessionStorage.getItem("noOrgModalViewed")) sessionStorage.removeItem("noOrgModalViewed");
                        };
                    };
                    getSaveLoaderDiv("profileForm", "userOrgs");
                    $(this).attr("save-container-id", "userOrgs");
                    assembleContent.demo(userId,true, $(this), true);
                    if (typeof reloadConsentList != "undefined") reloadConsentList();
                    tnthAjax.handleConsent($(this));
                });
            });
        }).fail(function() {
           // console.log("Problem retrieving data from server.");
           if ($(".get-orgs-error").length == 0) $(".error-message").append("<div class='get-orgs-error'>Server error occurred retrieving organization/clinic information.</div>");
            loader();
        });
    },
    "getConsent": function(userId, sync) {
       if (!userId) return false;
       $.ajax ({
            type: "GET",
            url: '/api/user/'+userId+"/consent",
            async: (sync ? false : true),
            cache: false
        }).done(function(data) {
            $(".get-consent-error").remove();
            if (data.consent_agreements) {
                var d = data["consent_agreements"];
                d.forEach(function(item) {
                    var orgId = item.organization_id;
                    //console.log("org Id: " + orgId);
                    var orgName = $("#" + orgId + "_org").attr("org_name");
                    if ($("#" + orgId + "_consent").length > 0) {
                        $("#" + orgId + "_consent").attr("checked", true);
                    };
                });
            };
           fillContent.consentList(data, userId, null, null);
           loader();
           return true;
        }).fail(function(xhr) {
            //console.log("Problem retrieving data from server.");
            fillContent.consentList(null, userId, "Problem retrieving data from server.<br/>Error Status Code: " + xhr.status + (xhr.status == 401 ? "<br/>Permission denied to access patient record": ""), xhr.status);
            loader();
            if ($(".get-consent-error").length == 0) $(".error-message").append("<div class='get-consent-error'>Server error occurred retrieving consent information.</div>");
            return false;
        });
    },
    "setConsent": function(userId, params, status, sync) {
        if (userId && params) {
            var consented = this.hasConsent(userId, params["org"], status);
            if (!consented) {
                $.ajax ({
                    type: "POST",
                    url: '/api/user/' + userId + '/consent',
                    contentType: "application/json; charset=utf-8",
                    cache: false,
                    dataType: 'json',
                    async: (sync? false: true),
                    data: JSON.stringify({"user_id": userId, "organization_id": params["org"], "agreement_url": params["agreementUrl"], "staff_editable": (hasValue(params["staff_editable"])? params["staff_editable"] : false), "include_in_reports": (hasValue(params["include_in_reports"]) ? params["include_in_reports"] : false), "send_reminders": (hasValue(params["send_reminders"]) ? params["send_reminders"] : false) })
                }).done(function(data) {
                    //console.log("consent updated successfully.");
                    $(".set-consent-error").remove();
                }).fail(function(xhr) {
                    //console.log("request to updated consent failed.");
                    //console.log(xhr.responseText)
                    if ($(".set-consent-error").length == 0) $(".error-message").append("<div class='set-consent-error'>Server error occurred setting consent status.</div>");
                });
            };
        };
    },
    deleteConsent: function(userId, params) {
        if (userId && params) {
            var consented = this.getAllValidConsent(userId, params["org"]);
            //console.log("has consent: " + consented)
            if (consented) {
                //delete all consents for the org
                consented.forEach(function(orgId) {
                    $.ajax ({
                        type: "DELETE",
                        url: '/api/user/' + userId + '/consent',
                        contentType: "application/json; charset=utf-8",
                        cache: false,
                        async: false,
                        dataType: 'json',
                        data: JSON.stringify({"organization_id": parseInt(orgId)})
                    }).done(function(data) {
                        //console.log("consent deleted successfully.");
                        $(".delete-consent-error").remove();
                    }).fail(function(xhr) {
                        //console.log("request to delete consent failed.");
                        //console.log(xhr.responseText)
                        if ($(".delete-consent-error").length == 0) $(".error-message").append("<div class='delete-consent-error'>Server error occurred removing consent.</div>");
                    });
                });

            };
        };
    },
    getAllValidConsent: function(userId, orgId) {
        //console.log("in hasConsent: userId: " + userId + " parentOrg: " + parentOrg)
        if (!userId) return false;
        if (!orgId) return false;

        var consentedOrgIds = [];
        //console.log("in hasConsent: userId: " + userId + " parentOrg: " + parentOrg)
        $.ajax ({
            type: "GET",
            url: '/api/user/'+userId+"/consent",
            async: false,
            cache: false
        }).done(function(data) {
            if (data.consent_agreements) {
                var d = data["consent_agreements"];
                if (d.length > 0) {
                    d.forEach(function(item) {
                        //console.log("expired: " + item.expires + " dateDiff: " + tnthDates.getDateDiff(item.expires))
                        expired = tnthDates.getDateDiff(item.expires);
                        if (!(item.deleted) && !(expired > 0)) {
                            if (orgId == item.organization_id) consentedOrgIds.push(orgId);
                        };
                    });
                };
            };

        }).fail(function() {
            return false;
        });
        //console.log(consentedOrgIds)
        return consentedOrgIds;
    },

    /****** NOTE - this will return the latest updated consent entry *******/
    hasConsent: function(userId, orgId, filterStatus) {
        //console.log("in hasConsent: userId: " + userId + " orgId: " + orgId)
        if (!userId) return false;
        if (!orgId) return false;

        var consentedOrgIds = [], expired = 0, found = false, suspended = false;
        //console.log("in hasConsent: userId: " + userId + " parentOrg: " + parentOrg)
        $.ajax ({
            type: "GET",
            url: '/api/user/'+userId+"/consent",
            async: false,
            cache: false
        }).done(function(data) {
            if (data.consent_agreements) {
                var d = data["consent_agreements"];
                if (d.length > 0) {
                    d = d.sort(function(a,b){
                        return new Date(b.signed) - new Date(a.signed); //latest comes first
                    });
                    item = d[0];
                    expired = tnthDates.getDateDiff(item.expires);
                    if (item.deleted) found = true;
                    if (expired > 0) found = true;
                    if (item.staff_editable && item.include_in_reports && !item.send_reminders) suspended = true;
                    if (!found) {
                        if (orgId == item.organization_id) {
                            //console.log("consented orgid: " + orgId)
                            switch(filterStatus) {
                                case "suspended":
                                    if (suspended) found = true;
                                    break;
                                case "purged":
                                    found = true;
                                    break;
                                case "consented":
                                    if (!suspended) {
                                        if (item.staff_editable && item.send_reminders && item.include_in_reports) found = true;
                                    };
                                    break;
                                default:
                                    found = true; //default is to return both suspended and consented entries
                            };
                            if (found) consentedOrgIds.push(orgId);

                        };
                    };
                }
            };

        }).fail(function() {
            return false;
         });
        //console.log(consentedOrgIds)
        return consentedOrgIds.length > 0 ? consentedOrgIds : null;
    },
    handleConsent: function(obj) {
        var self = this;
        $(obj).each(function() {
            var parentOrg = $(this).attr("data-parent-id");
            var parentName = $(this).attr("data-parent-name");
            var orgId = $(this).val();
            var userId = $("#fillOrgs").attr("userId");
            if (!hasValue(parentOrg)) parentOrg = $(this).closest(".org-container[data-parent-id]").attr("data-parent-id");
            if (!hasValue(parentName)) parentName = $(this).closest(".org-container[data-parent-id]").attr("data-parent-name");
            var cto = (typeof CONSENT_WITH_TOP_LEVEL_ORG != "undefined") && CONSENT_WITH_TOP_LEVEL_ORG;
            if ($(this).prop("checked")){
                if ($(this).attr("id") !== "noOrgs") {
                    if (parentOrg) {
                        var agreementUrl = $("#" + parentOrg + "_agreement_url").val();
                        if (agreementUrl && agreementUrl != "") {
                            var params = CONSENT_ENUM["consented"];
                            params.org = cto ? parentOrg : orgId;
                            params.agreementUrl = agreementUrl;
                            setTimeout("tnthAjax.setConsent($('#fillOrgs').attr('userId')," + JSON.stringify(params) + ", 'all', true);", 0);
                        };
                    };

                } else {
                    var pOrg, prevOrg, currentOrg;
                    if (cto) {
                        var topLevelOrgs = OT.getTopLevelOrgs();
                        topLevelOrgs.forEach(function(i) {
                            setTimeout("tnthAjax.deleteConsent($('#fillOrgs').attr('userId')," + JSON.stringify({"org": i}) + ");", 0);
                        });

                    } else {
                        //delete all orgs
                        $("#userOrgs").find("input[name='organization']").each(function() {
                            setTimeout("tnthAjax.deleteConsent($('#fillOrgs').attr('userId')," + JSON.stringify({"org": $(this).val()}) + ");", 0);
                        });
                    };
                };
            } else {
                //delete only when all the child orgs from the parent org are unchecked as consent agreement is with the parent org
                if (cto) {
                    var childOrgs = $("#userOrgs div.org-container[data-parent-id='" + parentOrg + "']").find("input[name='organization']");
                    var allUnchecked = true;
                    childOrgs.each(function() {
                        if ($(this).prop("checked")) allUnchecked = false;
                    });
                    if (allUnchecked) {
                        setTimeout("tnthAjax.deleteConsent($('#fillOrgs').attr('userId')," + JSON.stringify({"org": parentOrg}) + ");", 0);
                    };
                } else {
                    setTimeout("tnthAjax.deleteConsent($('#fillOrgs').attr('userId')," + JSON.stringify({"org": orgId}) + ");", 0);
                };
            };
        });
    },
    "getDemo": function(userId, noOverride, sync, callback) {
        $.ajax ({
            type: "GET",
            url: '/api/demographics/'+userId,
            async: (sync ? false: true)
        }).done(function(data) {
            if (!noOverride) {
                fillContent.race(data);
                fillContent.ethnicity(data);
                fillContent.indigenous(data);
                fillContent.orgs(data);
                fillContent.demo(data);
                fillContent.timezone(data);
                fillContent.subjectId(data);
            }
            $(".get-demo-error").remove();
            loader();
            if (callback) callback();
        }).fail(function() {
           // console.log("Problem retrieving data from server.");
            loader();
            if (callback) callback();
            if ($(".get-demo-error").length == 0) $(".error-message").append("<div class='get-demo-error'>Server error occurred retrieving demographics information.</div>");
        });
    },
    "putDemo": function(userId,toSend,targetField, sync) {
        flo.showLoader(targetField);
        $.ajax ({
            type: "PUT",
            url: '/api/demographics/'+userId,
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            async: (sync ? false: true),
            data: JSON.stringify(toSend)
        }).done(function(data) {
            //console.log("done");
            //console.log(data);
            $(".put-demo-error").remove();
            flo.showUpdate(targetField);
        }).fail(function() {
            if ($(".put-demo-error").length == 0) $(".error-message").append("<div class='put-demo-error'>Server error occurred setting demographics information.</div>");
            flo.showError(targetField);
        });
    },
    "getDob": function(userId) {
        $.ajax ({
            type: "GET",
            url: '/api/demographics/'+userId
        }).done(function(data) {
            fillContent.dob(data);
            //console.log(data)
            loader();
        }).fail(function() {
           // console.log("Problem retrieving data from server.");
            loader();
        });
    },
    "getName": function(userId) {
        $.ajax ({
            type: "GET",
            url: '/api/demographics/'+userId
        }).done(function(data) {
            fillContent.name(data);
            loader();
        }).fail(function() {
            loader();
        });
    },
    "hasTreatment": function(data) {
        var found = false;
        if (data && data.entry && data.entry.length > 0) {
            // sort from newest to oldest based on lsat updated date
            data.entry = data.entry.sort(function(a,b){
                return new Date(b.resource.meta.lastUpdated) - new Date(a.resource.meta.lastUpdated);
            });
            var found = false;
            (data.entry).forEach(function(item) {
                //console.log(item.resource.code.coding[0].code +  " " + item.resource.performedDateTime)
                if (!found) {
                    var resourceItemCode = item.resource.code.coding[0].code;
                    var system = item.resource.code.coding[0].system;
                    var procId = item.resource.id;

                   // console.log(resourceItemCode)
                   if ((resourceItemCode == CANCER_TREATMENT_CODE && (system == SNOMED_SYS_URL)) || (resourceItemCode == NONE_TREATMENT_CODE && (system == CLINICAL_SYS_URL))) {
                        found = {"code": resourceItemCode, "id": procId};
                    }

                };
            });
        };

        return found;
    },
    "getTreatment": function (userId) {
        if (!userId) return false;
        $.ajax ({
            type: "GET",
            url: '/api/patient/'+userId+'/procedure'
        }).done(function(data) {
            fillContent.treatment(data);
        }).fail(function() {
           // console.log("Problem retrieving data from server.");
           $("#userProcedures").html("<span class='text-danger'>Error retrieving data from server</span>");
        });
    },
    "postTreatment": function(userId, started, treatmentDate, targetField) {
        if (!userId) return false;
        tnthAjax.deleteTreatment(userId, targetField);
        var code = NONE_TREATMENT_CODE;
        var display = "None";
        var system = CLINICAL_SYS_URL;

        if (started) {
            code = CANCER_TREATMENT_CODE;
            display = "Procedure on prostate";
            system = SNOMED_SYS_URL;

        };

        if (!hasValue(treatmentDate)) {
            var date = new Date();
            //in yyyy-mm-dd format
            treatmentDate = date.getFullYear() + "-" + (date.getMonth() + 1) + "-" + date.getDate();
        };

        var procID = [{ "code": code, "display": display, "system": system }];
        var procArray = {};

        procArray["resourceType"] = "Procedure";
        procArray["subject"] = {"reference": "Patient/" + userId};
        procArray["code"] = {"coding": procID};
        procArray["performedDateTime"] = treatmentDate ? treatmentDate: "";

        tnthAjax.postProc(userId, procArray, targetField);
    },
    deleteTreatment: function(userId, targetField) {
        var self = this;
        $.ajax ({
            type: "GET",
            url: '/api/patient/'+userId+'/procedure',
            async: false
        }).done(function(data) {
            var treatmentData = self.hasTreatment(data);
            if (treatmentData) {
                if (treatmentData.code == CANCER_TREATMENT_CODE) {
                    tnthAjax.deleteProc(treatmentData.id, targetField, true);
                } else {
                    tnthAjax.deleteProc(treatmentData.id, targetField, true);
                };
            };
        }).fail(function() {
           // console.log("Problem retrieving data from server.");
        });
    },
    "getProc": function(userId,newEntry) {
        $.ajax ({
            type: "GET",
            url: '/api/patient/'+userId+'/procedure'
        }).done(function(data) {
            fillContent.proceduresContent(data,newEntry);
        }).fail(function() {
           // console.log("Problem retrieving data from server.");
        });
    },
    "postProc": function(userId,toSend, targetField) {
        flo.showLoader(targetField);
        $.ajax ({
            type: "POST",
            url: '/api/procedure',
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify(toSend)
        }).done(function(data) {
            flo.showUpdate(targetField);
            $(".get-procs-error").remove();
        }).fail(function() {
           // console.log("Problem updating procedure on server.");
            if ($(".get-procs-error").length == 0) $(".error-message").append("<div class='get-procs-error'>Server error occurred saving procedure/treatment information.</div>");
            flo.showError(targetField);
        });
    },
    "deleteProc": function(procedureId, targetField, sync) {
        flo.showLoader(targetField);
        $.ajax ({
            type: "DELETE",
            url: '/api/procedure/'+procedureId,
            contentType: "application/json; charset=utf-8",
            async: (sync ? false: true)
        }).done(function(data) {
            flo.showUpdate(targetField);
            $(".del-procs-error").remove();
        }).fail(function() {
            // console.log("Problem deleting procedure on server.");
            if ($(".del-procs-error").length == 0) $(".error-message").append("<div class='del-procs-error'>Server error occurred removing procedure/treatment information.</div>");
            flo.showError(targetField);
        });
    },
    "getRoleList": function() {
        $.ajax({
            type: "GET",
            url: "/api/roles",
            async: false
        }).done(function(data) {
            fillContent.roleList(data);
        });
    },
    "getRoles": function(userId,isProfile) {
        var self = this;
        $.ajax ({
            type: "GET",
            url: '/api/user/'+userId+'/roles'
        }).done(function(data) {
            //self.getRoleList();
            $(".get-roles-error").remove();
            fillContent.roles(data,isProfile);
        }).fail(function() {
           // console.log("Problem retrieving data from server.");
           if ($(".get-roles-error").length == 0) $(".error-message").append("<div class='get-roles-error'>Server error occurred retrieving user role information.</div>");
        });
    },
    "putRoles": function(userId,toSend) {
        $.ajax ({
            type: "PUT",
            url: '/api/user/'+userId+'/roles',
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify(toSend)
        }).done(function(data) {
            $(".put-roles-error").remove();
        }).fail(function(jhr) {
           if ($(".put-roles-error").length == 0) $(".error-message").append("<div class='put-roles-error'>Server error occurred setting user role information.</div>");
           //console.log(jhr.responseText);
        });
    },
    "deleteRoles": function(userId,toSend) {
        $.ajax ({
            type: "DELETE",
            url: '/api/user/'+userId+'/roles',
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify(toSend)
        }).done(function(data) {
            $(".delete-roles-error").remove();
        }).fail(function() {
           // console.log("Problem updating role on server.");
           if ($(".delete-roles-error").length == 0) $(".error-message").append("<div class='delete-roles-error'>Server error occurred deleting user role.</div>");

        });
    },
    "getClinical": function(userId) {
        $.ajax ({
            type: "GET",
            url: '/api/patient/'+userId+'/clinical'
        }).done(function(data) {
            $(".get-clinical-error").remove();
            fillContent.clinical(data);
        }).fail(function() {
           if ($(".get-clinical-error").length == 0) $(".error-message").append("<div class='get-clinical-error'>Server error occurred retrieving clinical data.</div>");
        });
    },
    "putClinical": function(userId, toCall, toSend, targetField) {
        flo.showLoader(targetField);
        $.ajax ({
            type: "POST",
            url: '/api/patient/'+userId+'/clinical/'+toCall,
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify({value: toSend})
        }).done(function() {
            $(".put-clinical-error").remove();
            flo.showUpdate(targetField);
        }).fail(function() {
            //alert("There was a problem saving your answers. Please try again.");
            if ($(".put-clinical-error").length == 0) $(".error-message").append("<div class='put-clinical-error'>Server error occurred updating clinical data.</div>");
            flo.showError(targetField);
        });
    },
    "postTerms": function(toSend) {
        $.ajax ({
            type: "POST",
            url: '/api/tou/accepted',
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify(toSend)
        }).done(function() {
           // console.log('terms stored');
           $(".post-tou-error").remove();
        }).fail(function() {
            //alert("There was a problem saving your answers. Please try again.");
            if ($(".post-tou-error").length == 0) $(".error-message").append("<div class='post-tou-error'>Server error occurred saving terms of use information.</div>");
        });
    }
};

function getIEVersion() {
    var match = navigator.userAgent.match(/(?:MSIE |Trident\/.*; rv:)(\d+)/);
    return match ? parseInt(match[1]) : undefined;
};

function newHttpRequest(url,callBack, noCache)
{
    attempts++;
    var xmlhttp;
    if (window.XDomainRequest)
    {
        xmlhttp=new XDomainRequest();
        xmlhttp.onload = function(){callBack(xmlhttp.responseText)};
    } else if (window.XMLHttpRequest) xmlhttp=new XMLHttpRequest();
    else xmlhttp=new ActiveXObject("Microsoft.XMLHTTP");
    xmlhttp.onreadystatechange=function()
    {
        if (xmlhttp.readyState==4) {
            if (xmlhttp.status==200) {
                if (callBack) callBack(xmlhttp.responseText);
            } else {
                if (attempts < 3) setTimeout ( function(){ newHttpRequest(url,callBack, noCache); }, 3000 );
                else loader();
            };
        };
    };
    if (noCache) url = url + ((/\?/).test(url) ? "&" : "?") + (new Date()).getTime();
    xmlhttp.open("GET",url,true);
    xmlhttp.send();
};

$.ajaxSetup({
    timeout: 2000,
    retryAfter:3000
});
var attempts = 0;

funcWrapper = function(param) {
    attempts++;
    $.ajax({
        url: PORTAL_NAV_PAGE,
        type:'GET',
        contentType:'text/plain',
        //dataFilter:data_filter,
        //xhr: xhr_function,
        crossDomain: true,
        cache: false
        //xhrFields: {withCredentials: true},
    }, 'html')
    .done(function(data) {
        embed_page(data);
        //showSearch();
    })
    .fail(function(jqXHR, textStatus, errorThrown) {
      //  console.log("Error loading nav elements from " + PORTAL_HOSTNAME);
        if (attempts < 3) {
            setTimeout ( function(){ funcWrapper( param ) }, $.ajaxSetup().retryAfter );
        } else loader();
    })
    .always(function() {
        loader();
    });
};

$(document).ready(function() {

    if (typeof PORTAL_NAV_PAGE != 'undefined') {

        loader(true);

        var isIE = getIEVersion();
        if (isIE) {
            newHttpRequest(PORTAL_NAV_PAGE, embed_page, true);
        } else {
            funcWrapper();
        };
    } else loader();

    // Reveal footer after load to avoid any flashes will above content loads
    $("#homeFooter").show();

    // To validate a form, add class to <form> and validate by ID.
    $('form.to-validate').validator({
        custom: {
            birthday: function($el) {
                var m = parseInt($("#month").val());
                var d = parseInt($("#date").val());
                var y = parseInt($("#year").val());
                // If all three have been entered, run check
                var goodDate = true;
                var errorMsg = "";
                // If NaN then the values haven't been entered yet, so we
                // validate as true until other fields are entered
                if (isNaN(y) || (isNaN(d) && isNaN(y))) {
                    $("#errorbirthday").html('All fields must be complete.').hide();
                    goodDate = false;
                } else if (isNaN(d)) {
                    errorMsg = "Please enter a valid date.";
                } else if (isNaN(m)) {
                    errorMsg += (hasValue(errorMsg)?"<br/>": "") + "Please enter a valid month.";
                } else if (isNaN(y)) {
                    errorMsg += (hasValue(errorMsg)?"<br/>": "") + "Please enter a valid year.";
                };

                if (hasValue(errorMsg)) {
                    $("#errorbirthday").html(errorMsg).show();
                    $("#birthday").val("");
                    goodDate = false;
                }
                //}
                //console.log("good Date: " + goodDate + " errorMessage; " + errorMsg)
                if (goodDate) {
                    $("#errorbirthday").html("").hide();
                };

                return goodDate;
            },
            customemail: function($el) {
                var emailVal = $.trim($el.val());
                if (emailVal == "") {
                    return false;
                }
                var emailReg = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
                // Add user_id to api call (used on patient_profile page so that staff can edit)
                var addUserId = "";
                if (typeof(patientId) !== "undefined") {
                    addUserId = "&user_id="+patientId;
                }
                // If this is a valid address, then use unique_email to check whether it's already in use
                if (emailReg.test(emailVal)) {
                    $.ajax ({
                        type: "GET",
                        //url: '/api/unique_email?email='+encodeURIComponent($el.val())+addUserId
                        url: '/api/unique_email?email='+encodeURIComponent(emailVal)+addUserId
                    }).done(function(data) {
                        if (data.unique) {
                            $("#erroremail").html('').parents(".form-group").removeClass('has-error');
                            if ($el.attr("update-on-validated") == "true" && $el.attr("user-id")) {
                                assembleContent.demo($el.attr("user-id"),true, $el);
                            };
                        } else {
                            $("#erroremail").html("This e-mail address is already in use. Please enter a different address.").parents(".form-group").addClass('has-error');
                        }
                    }).fail(function() {
                        console.log("Problem retrieving data from server.")
                    });
                }
                return emailReg.test(emailVal);
            }
        },
        errors: {
            birthday: "Sorry, this isn't a valid date. Please try again.",
            customemail: "This isn't a valid e-mail address, please double-check."
        },
        disable: false
    }).off('input.bs.validator'); // Only check on blur (turn off input)   to turn off change - change.bs.validator

});

var tnthDates = {
    /** validateBirthDate  check whether the date is a sensible date.
     ** NOTE this can replace the custom validation check; hook this up to the onchange/blur event of birthday field
     ** work better in conjunction with HTML5 native validation check on the field e.g. required, pattern match  ***/
    "validateBirthDate": function(m, d, y) {
        if (hasValue(m) && hasValue(d) && hasValue(y)) {

            var m = parseInt(m);
            var d = parseInt(d);
            var y = parseInt(y);

            if (!(isNaN(m)) && !(isNaN(d)) && !(isNaN(y))) {
                var today = new Date();
                // Check to see if this is a real date
                var date = new Date(y,m-1,d);
                if (!(date.getFullYear() == y && (date.getMonth() + 1) == m && date.getDate() == d)) {
                    $("#errorbirthday").html("Invalid date. Please try again.").show();
                    return false;
                }
                else if (date.setHours(0,0,0,0) >= today.setHours(0,0,0,0)) {
                    $("#errorbirthday").html("Birthday must not be in the future. Please try again.").show();
                    return false; //shouldn't be in the future
                }
                else if (y < 1900) {
                    $("#errorbirthday").html("Date must not be before 1900. Please try again.").show();
                    return false;
                };

                $("#errorbirthday").html("").hide();

                return true;

            } else return false;

        } else {
            return false;
        };
    },
    /***
     * changeFormat - changes date format, particularly for submitting to server
     * @param currentDate - date to change
     * @param reverse - use to switch from yyyy-mm-dd to dd/mm/yyyy
     * @param shorten - removes padding from zeroes (only in reverse)
     * @returns - a date as a string
     *
     * Examples:
     * changeFormat("29/04/2016") returns "2016-04-29T07:00:00", converts according to getTimezoneOffset
     * changeFormat("2016-04-29",true) returns "29/04/2016"
     * changeFormat("2016-04-29",true,true) returns "29/04/2016"
     ***/
    "changeFormat": function(currentDate,reverse,shorten) {
        if (currentDate == null || currentDate == "") {
            return null;
        }
        var yearToPass, convertDate, dateFormatArray;
        if (reverse) {
            dateFormatArray = currentDate.split("-");
            if (!dateFormatArray || (dateFormatArray.length == 0)) return null;
            yearToPass = dateFormatArray[0];
            if (shorten) {
                dateFormatArray[1] = dateFormatArray[1].replace(/^0+/, '');
                dateFormatArray[2] = dateFormatArray[2].replace(/^0+/, '');
            }
            convertDate = dateFormatArray[2]+"/"+dateFormatArray[1]+"/"+yearToPass;
        } else {
            dateFormatArray = currentDate.split("/");
            if (!dateFormatArray || (dateFormatArray.length == 0)) return null;
            // If patient manuals enters two digit year, then add 19 or 20 to year.
            // TODO - this is susceptible to Y2K for 2100s. Be better to force
            // user to type 4 digits.
            var currentTime = new Date();
            if (dateFormatArray[2].length == 2) {
                var shortYear = currentTime.getFullYear().toString().substr(2,2);
                if (dateFormatArray[2] > shortYear) {
                    yearToPass = '19'+dateFormatArray[2];
                } else {
                    yearToPass = '20'+dateFormatArray[2];
                }
            } else {
                yearToPass = dateFormatArray[2];
            }
            convertDate = yearToPass+"-"+dateFormatArray[1]+"-"+dateFormatArray[0]
            // add T according to timezone
            var tzOffset = currentTime.getTimezoneOffset();//minutes
            tzOffset /= 60;//hours
            if (tzOffset < 10) tzOffset = "0" + tzOffset;
            convertDate += "T" + tzOffset + ":00:00";
        }
        return convertDate
    },
    /**
     * Simply swaps:
     *      a/b/cdef to b/a/cdef
     *      (single & double digit permutations accepted...)
     *      ab/cd/efgh to cd/ab/efgh
     * Does not check for valid dates on input or output!
     * @param currentDate string eg 7/4/1976
     * @returns string eg 4/7/1976
     */
    "swap_mm_dd": function(currentDate) {
        var splitDate = currentDate.split('/');
        return splitDate[1] + '/' + splitDate[0] + '/' + splitDate[2];
    },
    /***
     * parseDate - Fancier function for changing javascript date yyyy-mm-dd (with optional time) to a dd/mm/yyyy (optional time) format. Used with mPOWEr
     * @param date - the date to be converted
     * @param noReplace - prevent replacing any spaces with "T" to get in proper javascript format. 2016-02-24 15:28:09-0800 becomes 2016-02-24T15:28:09-0800
     * @param padZero - if true, will add padded zero to month and date
     * @param keepTime - if true, will output the time as part of the date
     * @param blankText - pass a value to display if date is null
     * @returns date as a string with optional time
     *
     * parseDate("2016-02-24T15:28:09-0800",true,false,true) returns "24/2/2016 3:28pm"
     */
    "parseDate": function(date,noReplace,padZero,keepTime,blankText) {
        if(date == null) {
            if (blankText) {
                return blankText;
            } else {
                return "";
            }
        }
        // Put date in proper javascript format
        if (noReplace == null) {
            date = date.replace(" ", "T");
        }
        // Need to reformat dates b/c of date format issues in Safari (and others?)
        // http://stackoverflow.com/questions/6427204/date-parsing-in-javascript-is-different-between-safari-and-chrome
        var a = date.split(/[^0-9]/);
        var toConvert;
        if (a[3]) {
            toConvert=new Date (a[0],a[1]-1,a[2],a[3],a[4],a[5]);
        } else {
            toConvert=new Date (a[0],a[1]-1,a[2]);
        }

        // Switch date to mm/dd/yyyy
        //var toConvert = new Date(Date.parse(date));
        var month = toConvert.getMonth() + 1;
        var day = toConvert.getDate();
        if (padZero) {
            if (month <= 9)
                month = '0' + month;
            if (day <= 9)
                day = '0' + day;
        }
        if (keepTime) {
            var amPm = "am";
            var hour = a[3];
            if (a[3] > 11) {
                amPm = "pm";
                if (a[3] > 12) {
                    hour = (a[3]-12);
                }
            }
            return day + "/" + month + "/" + toConvert.getFullYear()+" "+hour+":"+a[4]+amPm;
        } else {
            return day + "/" + month + "/" + toConvert.getFullYear();
        }
    },
    /***
     * parseForSorting - changes date to a YYYYMMDDHHMMSS string for sorting (note that this is a string rather than a number)
     * @param date - the date to be converted
     * @param noReplace - prevent replacing any spaces with "T" to get in proper javascript format. 2016-02-24 15:28:09-0800 becomes 2016-02-24T15:28:09-0800. Adding T indicates UTC time
     * @returns date as a string used by system for sorting
     *
     * parseDate("2016-02-24T15:28:09-0800",true) returns "201600224152809"
     */
    "parseForSorting": function(date,noReplace) {
        if (date == null) {
            return ""
        }
        // Put date in proper javascript format
        if (noReplace == null) {
            date = date.replace(" ", "T");
        }
        // Need to reformat dates b/c of date format issues in Safari (and others?)
        // http://stackoverflow.com/questions/6427204/date-parsing-in-javascript-is-different-between-safari-and-chrome
        var a = date.split(/[^0-9]/);
        var toConvert=new Date (a[0],a[1]-1,a[2],a[3],a[4],a[5]);
        // Switch date to mm/dd/yyyy
        //var toConvert = new Date(Date.parse(date));
        var month = toConvert.getMonth() + 1;
        var day = toConvert.getDate();
        if (month <= 9)
            month = '0' + month;
        if (day <= 9)
            day = '0' + day;
        return toConvert.getFullYear() + month + day + a[3] + a[4] + a[5]

    },
    /***
     * spellDate - spells out date in a format based on language/local. Currently not in use.
     * @param passDate - date to use. If empty, defaults to today.
     * @param ymdFormat - false by default. false = dd/mm/yyyy. true = yyyy-mm-dd
     * @returns spelled out date, localized
     */
    "spellDate": function(passDate,ymdFormat) {
        var todayDate = new Date();
        if (passDate) {
            // ymdFormat is true, we are assuming it's being received as YYYY-MM-DD
            if (ymdFormat) {
                todayDate = passDate.split("-");
                todayDate = new Date(todayDate[2], todayDate[0] - 1, todayDate[1])
            } else {
                // Otherwide dd/mm/yyyy
                todayDate = passDate.split("/");
                todayDate = new Date(todayDate[2], todayDate[1] - 1, todayDate[0])
            }
        }
        var returnDate;
        var monthNames = ["January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        // If user's language is Spanish then use dd/mm/yyyy format and changes words
        if (userSetLang !== undefined && userSetLang == 'es_MX') {
            monthNames = ["enero","febrero","marzo","abril","mayo","junio","julio", "agosto","septiembre","octubre","noviembre","diciembre"];
            returnDate = ('0' + todayDate.getDate()).slice(-2)+" de "+monthNames[todayDate.getMonth()]+" de "+todayDate.getFullYear()
        } else if(userSetLang !== undefined && userSetLang == "en_AU") {
            returnDate = ('0' + todayDate.getDate()).slice(-2)+" "+monthNames[todayDate.getMonth()]+" "+todayDate.getFullYear()
        } else {
            returnDate = monthNames[todayDate.getMonth()]+" "+('0' + todayDate.getDate()).slice(-2)+", "+todayDate.getFullYear()
        }
        return returnDate
    },
    /***
     * Calculates number of days between two dates. Used in mPOWEr for surgery/discharge
     * @param startDate - required. Assumes YYYY-MM-DD. This is typically the date of surgery or discharge
     * @param dateToCalc - optional. If empty, then assumes today's date
     * @returns number of days
     */
    "getDateDiff": function(startDate,dateToCalc) {
        var a = startDate.split(/[^0-9]/);
        var dateTime = new Date(a[0], a[1]-1, a[2]).getTime();
        var d;
        if (dateToCalc) {
            var c = dateToCalc.split(/[^0-9]/);
            d = new Date(c[0], c[1]-1, c[2]).getTime()
        } else {
            // If no baseDate, then use today to find the number of days between dateToCalc and today
            d = new Date().getTime()
        }
        // Round down to floor so we don't add an extra day if session is 12+ hours into the day
        return Math.floor((d - dateTime) / (1000 * 60 * 60 * 24))
    },
    "getAge": function (birthDate, otherDate) {
        birthDate = new Date(birthDate);
        // Use today's date to calc, unless otherwise specified
        var secondDate = new Date();
        if (otherDate) {
            secondDate = new Date(otherDate);
        }
        var years = (secondDate.getFullYear() - birthDate.getFullYear());

        if (secondDate.getMonth() < birthDate.getMonth() ||
            secondDate.getMonth() == birthDate.getMonth() && secondDate.getDate() < birthDate.getDate()) {
            years--;
        }
        return years;
    },
    /***
     * Simple function to add "days" label to a number of days. Not localized, used for mPOWEr
     * @param dateVal - required. Often derived via getDateDiff
     * @returns {string}
     */
    "addDays": function(dateVal) {
        var toReturn = "N/A";
        if (dateVal && typeof dateVal != undefined) {
            if (dateVal == 1) {
                toReturn = "1 day";
            } else if (dateVal < 0) {
                toReturn = "--";
            } else {
                toReturn = dateVal + " days";
            }
        } else if (dateVal === 0) {
            toReturn = "Today";
        }
        return toReturn
    }
};

/***
 * Bootstrap datatables functions
 * Uses http://bootstrap-table.wenzhixin.net.cn/documentation/
 ****/

var tnthTables = {
    /***
     * Quick way to sort when text is wrapper in an <a href> or other tag
     * @param a,b - the two items to compare
     * @returns 1,-1 or 0 for sorting
     */
    "stripLinksSorter": function(a,b) {
        a = $(a).text();
        b = $(b).text();
        var aa = parseFloat(a);
        var bb = parseFloat(b);
        //if (aa > bb) return 1;
        //if (aa < bb) return -1;
        //return 0;
        return  bb - aa;
    }
};

/*assume dateString is ISO-8601 formatted date returned from server: e.g. '2011-06-29T16:52:48.000Z'*/
function convertGMTToLocalTime(dateString, format) {
    if (dateString) {
           //console.log('unformated date: ' + dateString);
           var d = new Date(String(dateString));
            //console.log("new date: " + d)
           // console.log((new Date(d)).toString().replace(/GMT.*/g,""));
           var ap = "AM";
           var day = d.getDate();
           var month = (d.getMonth() + 1);
           var year = d.getFullYear();
           var hours = d.getHours();
           var minutes = d.getMinutes();
           var seconds = d.getSeconds();
           var nd = "";


           if (hours   > 11) { ap = "PM";             };
           if (hours   > 12) { hours = hours - 12;      };
           if (hours   === 0) { hours = 12;};

           day = pad(day);
           month = pad(month);
           hours = pad(hours);
           minutes = pad(minutes);
           seconds = pad(seconds);

           function pad(n) {
                n = parseInt(n);
                return (n < 10) ? '0' + n : n;
           };

           switch(format) {
                case "dd/mm/yyyy":
                    nd = day + "/" + month + "/" + year;
                    break;
                case "dd/mm/yyyy hh:mm:ss":
                    nd = day + "/" + month + "/" + year + " " + hours + ":" + minutes + ":" + seconds + " " + ap;
                    break;
                case "dd-mm-yyyy":
                    nd = day + "-" + month + "-" + year;
                    break;
                case "dd-mm-yyyy hh:mm:ss":
                    nd = day + "-" + month + "-" + year + " " + hours + ":" + minutes + ":" + seconds + " " + ap;
                    break;
                default:
                    //yyyy-mm-dd hh:mm:ss;
                    nd = year + "-" + month + "-" + day + " " + hours + ":" + minutes + ":" + seconds + " " + ap;
           }

           return nd;
    } else return "";


};

/**
 * Protect window.console method calls, e.g. console is not defined on IE
 * unless dev tools are open, and IE doesn't define console.debug
 */
(function() {
    var console = (window.console = window.console || {});
    var noop = function () {};
    var log = console.log || noop;
    var start = function(name) { return function(param) { log("Start " + name + ": " + param); } };
    var end = function(name) { return function(param) { log("End " + name + ": " + param); } };

    var methods = {
        // Internet Explorer (IE 10): http://msdn.microsoft.com/en-us/library/ie/hh772169(v=vs.85).aspx#methods
        // assert(test, message, optionalParams), clear(), count(countTitle), debug(message, optionalParams), dir(value, optionalParams), dirxml(value), error(message, optionalParams), group(groupTitle), groupCollapsed(groupTitle), groupEnd([groupTitle]), info(message, optionalParams), log(message, optionalParams), msIsIndependentlyComposed(oElementNode), profile(reportName), profileEnd(), time(timerName), timeEnd(timerName), trace(), warn(message, optionalParams)
        // "assert", "clear", "count", "debug", "dir", "dirxml", "error", "group", "groupCollapsed", "groupEnd", "info", "log", "msIsIndependentlyComposed", "profile", "profileEnd", "time", "timeEnd", "trace", "warn"

        // Safari (2012. 07. 23.): https://developer.apple.com/library/safari/#documentation/AppleApplications/Conceptual/Safari_Developer_Guide/DebuggingYourWebsite/DebuggingYourWebsite.html#//apple_ref/doc/uid/TP40007874-CH8-SW20
        // assert(expression, message-object), count([title]), debug([message-object]), dir(object), dirxml(node), error(message-object), group(message-object), groupEnd(), info(message-object), log(message-object), profile([title]), profileEnd([title]), time(name), markTimeline("string"), trace(), warn(message-object)
        // "assert", "count", "debug", "dir", "dirxml", "error", "group", "groupEnd", "info", "log", "profile", "profileEnd", "time", "markTimeline", "trace", "warn"

        // Firefox (2013. 05. 20.): https://developer.mozilla.org/en-US/docs/Web/API/console
        // debug(obj1 [, obj2, ..., objN]), debug(msg [, subst1, ..., substN]), dir(object), error(obj1 [, obj2, ..., objN]), error(msg [, subst1, ..., substN]), group(), groupCollapsed(), groupEnd(), info(obj1 [, obj2, ..., objN]), info(msg [, subst1, ..., substN]), log(obj1 [, obj2, ..., objN]), log(msg [, subst1, ..., substN]), time(timerName), timeEnd(timerName), trace(), warn(obj1 [, obj2, ..., objN]), warn(msg [, subst1, ..., substN])
        // "debug", "dir", "error", "group", "groupCollapsed", "groupEnd", "info", "log", "time", "timeEnd", "trace", "warn"

        // Chrome (2013. 01. 25.): https://developers.google.com/chrome-developer-tools/docs/console-api
        // assert(expression, object), clear(), count(label), debug(object [, object, ...]), dir(object), dirxml(object), error(object [, object, ...]), group(object[, object, ...]), groupCollapsed(object[, object, ...]), groupEnd(), info(object [, object, ...]), log(object [, object, ...]), profile([label]), profileEnd(), time(label), timeEnd(label), timeStamp([label]), trace(), warn(object [, object, ...])
        // "assert", "clear", "count", "debug", "dir", "dirxml", "error", "group", "groupCollapsed", "groupEnd", "info", "log", "profile", "profileEnd", "time", "timeEnd", "timeStamp", "trace", "warn"
        // Chrome (2012. 10. 04.): https://developers.google.com/web-toolkit/speedtracer/logging-api
        // markTimeline(String)
        // "markTimeline"

        assert: noop, clear: noop, trace: noop, count: noop, timeStamp: noop, msIsIndependentlyComposed: noop,
        debug: log, info: log, log: log, warn: log, error: log,
        dir: log, dirxml: log, markTimeline: log,
        group: start('group'), groupCollapsed: start('groupCollapsed'), groupEnd: end('group'),
        profile: start('profile'), profileEnd: end('profile'),
        time: start('time'), timeEnd: end('time')
    };

    for (var method in methods) {
        if ( methods.hasOwnProperty(method) && !(method in console) ) { // define undefined methods as best-effort methods
            console[method] = methods[method];
        }
    }
})();


var FieldLoaderHelper = function () {
    this.showLoader = function(targetField) {
        if(targetField && targetField.length > 0) {
           $("#" + targetField.attr("save-container-id") + "_load").css("opacity", 1);
        };
    };

    this.showUpdate = function(targetField) {
        if(targetField && targetField.length > 0) {
             $("#" + targetField.attr("save-container-id") + "_error").text("").css("opacity", 0);
             $("#"+ targetField.attr("save-container-id") + "_success").text("success");
            setTimeout('$("#' + targetField.attr("save-container-id") + '_load").css("opacity", 0);', 600);
            setTimeout('$("#'+ targetField.attr("save-container-id") + '_success").css("opacity", 1);', 900);
            setTimeout('$("#' + targetField.attr("save-container-id") + '_success").css("opacity", 0);', 2000);
        };
    };

    this.showError = function(targetField) {
        if(targetField && targetField.length > 0) {
            $("#" + targetField.attr("save-container-id") + "_error").html("Unable to update. System/Server Error.");
            $("#" + targetField.attr("save-container-id") + "_success").text("").css("opacity", 0);
            setTimeout('$("#' + targetField.attr("save-container-id") + '_load").css("opacity", 0);', 600);
            setTimeout('$("#'+ targetField.attr("save-container-id") + '_error").css("opacity", 1);', 900);
            setTimeout('$("#' + targetField.attr("save-container-id") + '_error").css("opacity", 0);', 5000);
        };
    };

};

var flo = new FieldLoaderHelper();

function getSaveLoaderDiv(parentID, containerID) {
    var el = $("#" + containerID + "_load");
    if (el.length == 0) $("#" + parentID + " #" + containerID).after('<div class="load-container">' + '<i id="' + containerID + '_load" class="fa fa-spinner fa-spin load-icon fa-lg save-info" style="margin-left:4px; margin-top:5px" aria-hidden="true"></i><i id="' + containerID + '_success" class="fa fa-check success-icon save-info" style="color: green" aria-hidden="true">Updated</i><i id="' + containerID + '_error" class="fa fa-times error-icon save-info" style="color:red" aria-hidden="true">Unable to Update.System error.</i></div>');
};

function _isTouchDevice(){
    return true == ("ontouchstart" in window || window.DocumentTouch && document instanceof DocumentTouch);
};

function hasValue(val) {
    return val != null && val != "" && val != "undefined";
};

function isString (obj) {
  return (Object.prototype.toString.call(obj) === '[object String]');
};
var __winHeight = $(window).height(), __winWidth = $(window).width();
$.fn.isOnScreen = function(){
    var viewport = {};
    viewport.top = $(window).scrollTop();
    viewport.bottom = viewport.top + __winHeight;
    var bounds = {};
    bounds.top = this.offset().top;
    bounds.bottom = bounds.top + this.outerHeight();
    return ((bounds.top <= viewport.bottom) && (bounds.bottom >= viewport.top));
};
//Promise polyfill - IE doesn't support Promise - so need this
!function(e){function n(){}function t(e,n){return function(){e.apply(n,arguments)}}function o(e){if("object"!=typeof this)throw new TypeError("Promises must be constructed via new");if("function"!=typeof e)throw new TypeError("not a function");this._state=0,this._handled=!1,this._value=void 0,this._deferreds=[],s(e,this)}function i(e,n){for(;3===e._state;)e=e._value;return 0===e._state?void e._deferreds.push(n):(e._handled=!0,void o._immediateFn(function(){var t=1===e._state?n.onFulfilled:n.onRejected;if(null===t)return void(1===e._state?r:u)(n.promise,e._value);var o;try{o=t(e._value)}catch(i){return void u(n.promise,i)}r(n.promise,o)}))}function r(e,n){try{if(n===e)throw new TypeError("A promise cannot be resolved with itself.");if(n&&("object"==typeof n||"function"==typeof n)){var i=n.then;if(n instanceof o)return e._state=3,e._value=n,void f(e);if("function"==typeof i)return void s(t(i,n),e)}e._state=1,e._value=n,f(e)}catch(r){u(e,r)}}function u(e,n){e._state=2,e._value=n,f(e)}function f(e){2===e._state&&0===e._deferreds.length&&o._immediateFn(function(){e._handled||o._unhandledRejectionFn(e._value)});for(var n=0,t=e._deferreds.length;n<t;n++)i(e,e._deferreds[n]);e._deferreds=null}function c(e,n,t){this.onFulfilled="function"==typeof e?e:null,this.onRejected="function"==typeof n?n:null,this.promise=t}function s(e,n){var t=!1;try{e(function(e){t||(t=!0,r(n,e))},function(e){t||(t=!0,u(n,e))})}catch(o){if(t)return;t=!0,u(n,o)}}var a=setTimeout;o.prototype["catch"]=function(e){return this.then(null,e)},o.prototype.then=function(e,t){var o=new this.constructor(n);return i(this,new c(e,t,o)),o},o.all=function(e){var n=Array.prototype.slice.call(e);return new o(function(e,t){function o(r,u){try{if(u&&("object"==typeof u||"function"==typeof u)){var f=u.then;if("function"==typeof f)return void f.call(u,function(e){o(r,e)},t)}n[r]=u,0===--i&&e(n)}catch(c){t(c)}}if(0===n.length)return e([]);for(var i=n.length,r=0;r<n.length;r++)o(r,n[r])})},o.resolve=function(e){return e&&"object"==typeof e&&e.constructor===o?e:new o(function(n){n(e)})},o.reject=function(e){return new o(function(n,t){t(e)})},o.race=function(e){return new o(function(n,t){for(var o=0,i=e.length;o<i;o++)e[o].then(n,t)})},o._immediateFn="function"==typeof setImmediate&&function(e){setImmediate(e)}||function(e){a(e,0)},o._unhandledRejectionFn=function(e){"undefined"!=typeof console&&console&&console.warn("Possible Unhandled Promise Rejection:",e)},o._setImmediateFn=function(e){o._immediateFn=e},o._setUnhandledRejectionFn=function(e){o._unhandledRejectionFn=e},"undefined"!=typeof module&&module.exports?module.exports=o:e.Promise||(e.Promise=o)}(this);

