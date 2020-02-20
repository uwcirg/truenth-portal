import tnthAjax from "./TnthAjax.js";
import tnthDates from "./TnthDate.js";
import SYSTEM_IDENTIFIER_ENUM from "./SYSTEM_IDENTIFIER_ENUM";
import Utility from "./Utility.js";
export default { /*global $ i18next */
    update: function(subjectId, callback) {
        callback = callback || function() {};
        if (!subjectId) {
            callback({error: i18next.t("Subject id is required")});
            return;
        }
        var self = this;
        tnthAjax.getTreatment(subjectId, {useWorker:true}, function(data) {
            self.updateTreatmentElements(data);
            tnthAjax.getClinical(subjectId,{useWorker:true, data:{patch_dstu2: true}}, function(data) {
                self.updateClinical(data.entry);
                callback();
            });
        });
    },
    updateClinical: function(data) {
        if (!data) { return false; }
        var sortedArray = data.sort(function(a, b) {
            return b.resource.id - a.resource.id;
        });
        for (var i = 0; i < sortedArray.length; i++) {
            let val = sortedArray[i];
            let clinicalItem = String(val.resource.code.coding[0].display);
            let clinicalValue = val.resource.valueQuantity.value;
            let clinicalUnit = val.resource.valueQuantity.units;
            let truesyValue = parseInt(clinicalValue) === 1 && !clinicalUnit;
            let falsyValue = parseInt(clinicalValue) === 0 && !clinicalUnit;
            let status = val.resource.status;
            if (clinicalItem === "PCa diagnosis") {
                clinicalItem = "pca_diag";
            } else if (clinicalItem === "PCa localized diagnosis") {
                clinicalItem = "pca_localized";
            }
            let ci = $("div[data-topic='" + clinicalItem + "']");
            if (ci.length > 0) {
                ci.fadeIn();
            }
            let $radios = $("input:radio[name='" + clinicalItem + "']");
            if ($radios.length > 0) {
                if (!$radios.is(":checked")) {
                    if (String(status) === "unknown") {
                        $radios.filter("[data-status='unknown']").prop("checked", true);
                    } else {
                        $radios.filter("[value=" + clinicalValue + "]").not("[data-status='unknown']").prop("checked", true);
                    }
                    if (truesyValue) {
                        $radios.filter("[value=true]").prop("checked", true);
                    } else if (falsyValue) {
                        $radios.filter("[value=false]").prop("checked", true);
                    }
                    if (clinicalItem === "biopsy") {
                        if (String(clinicalValue) === "true" || truesyValue) {
                            if (val.resource.issued) {
                                var dString = tnthDates.formatDateString(val.resource.issued, "iso-short");
                                var dArray = dString.split("-");
                                $("#biopsyDate").val(dString);
                                $("#biopsy_year").val(dArray[0]);
                                $("#biopsy_month").val(dArray[1]);
                                $("#biopsy_day").val(dArray[2]);
                                $("#biopsyDateContainer").show();
                            }
                        } else {
                            $("#biopsyDate").val("");
                            $("#biopsyDateContainer").hide();
                        }
                    }
                    let parentContainer = $radios.parents(".pat-q");
                    if (String(clinicalValue) === "true" || truesyValue) {
                        parentContainer.next().fadeIn(150);
                    }
                    if (parentContainer.attr("data-next")) {
                        $("#patientQ [data-topic='"+parentContainer.attr("data-next")+"']").fadeIn(150);
                    }
                }
            }
        }
    },
    updateTreatmentElements: function(data) {
        var treatmentCode = tnthAjax.hasTreatment(data);
        if (treatmentCode) {
            var hasCancerTreatment = String(treatmentCode) === String(SYSTEM_IDENTIFIER_ENUM.CANCER_TREATMENT_CODE);
            $("#tx_yes").prop("checked", hasCancerTreatment);
            $("#tx_no").prop("checked", !hasCancerTreatment);
            let ci = $("div[data-topic='tx']");
            if (ci.length > 0) {
                ci.fadeIn();
            }
        }
    },
    initFieldEvents: function(subjectId) {
        $("#patientQ [name='biopsy']").on("click", function() {
            let toSend = String($(this).val()), biopsyDate = $("#biopsyDate").val(), thisItem = $(this), userId = subjectId;
            let toCall = thisItem.attr("name") || thisItem.attr("data-name"), targetField = $("#patientQ");
            let arrQ = ["pca_diag", "pca_localized", "tx"];
            if (toSend === "true") {
                $("#biopsyDateContainer").show();
                $("#biopsyDate").attr("skipped", "false");
                arrQ.forEach(function(fieldName) {
                    $("#patientQ input[name='" + fieldName + "']").attr("skipped", "false");
                });
                if (biopsyDate) {
                    setTimeout(function() {
                        tnthAjax.postClinical(userId, toCall, toSend, "", targetField, {"issuedDate": biopsyDate});
                    }, 50);
                } else {
                    $("#biopsy_day").focus();
                }
            } else {
                $("#biopsyDate").attr("skipped", "true");
                $("#biopsyDate, #biopsy_day, #biopsy_month, #biopsy_year").val("");
                $("#biopsyDateError").text("");
                $("#biopsyDateContainer").hide();
                arrQ.forEach(function(fieldName) {
                    var field = $("#patientQ input[name='" + fieldName + "']");
                    field.prop("checked", false);
                    field.attr("skipped", "true");
                });
                setTimeout(function() {
                    tnthAjax.postClinical(userId, toCall, "false", thisItem.attr("data-status"), targetField);
                    tnthAjax.postClinical(userId, "pca_diag", "false", "", targetField);
                    tnthAjax.postClinical(userId, "pca_localized", "false", "", targetField);
                    tnthAjax.deleteTreatment(userId, "", function() {
                        tnthAjax.postTreatment(userId, false, "", $("#patientQ")); //should post no treatment started
                    });
                }, 50);

            }
        });
        Utility.convertToNumericField($("#biopsy_day, #biopsy_year"));
        $("#biopsy_day, #biopsy_month, #biopsy_year").on("change", function() {
            let d = $("#biopsy_day").val(), m = $("#biopsy_month").val(), y = $("#biopsy_year").val();
            let isValid = tnthDates.validateDateInputFields(m, d, y, "biopsyDateError");
            if (isValid) {
                $("#biopsyDate").val(y+"-"+m+"-"+d);
                $("#biopsyDateError").text("").hide();
                $("#biopsy_yes").trigger("click");
            } else {
                $("#biopsyDate").val("");
            }
        });

        $("#patientQ input[name='tx']").on("click", function() {
            tnthAjax.postTreatment(subjectId, (String($(this).val()) === "true"), "", $("#patientQ"));
        });

        $("#patientQ input[name='pca_localized']").on("click", function() {
            let o = $(this);
            setTimeout(function() {
                tnthAjax.postClinical(subjectId, o.attr("name"), o.val(), o.attr("data-status"), $("#patientQ"));
            }, 50);
        });

        $("#patientQ input[name='pca_diag']").on("click", function() {
            let toSend = String($(this).val()), userId = subjectId, o = $(this), targetField = $("#patientQ");
            setTimeout(function() {
                tnthAjax.postClinical(userId, o.attr("name"), toSend, o.attr("data-status"), targetField);
            }, 50);
            if (toSend !== "true") {
                ["pca_localized", "tx"].forEach(function(fieldName) {
                    var field = $("#patientQ input[name='" + fieldName + "']");
                    field.prop("checked", false);
                    field.attr("skipped", "true");
                });
                setTimeout(function() {
                    tnthAjax.postClinical(userId, "pca_localized", "false", "", targetField);
                    tnthAjax.deleteTreatment(userId, "", function() {
                        tnthAjax.postTreatment(userId, false, "", $("#patientQ")); //should post no treatment started
                    });
                }, 50);
            }
        });
    }
};
