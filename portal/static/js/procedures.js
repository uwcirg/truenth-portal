$.fn.extend({
    // Special type of select question - passes two values - the answer from
    // the select plus an associated date from a separate input
    eventInput: function(settings) {

        $(this).on("click", function() {

            // First disable button to prevent double-clicks
            $(this).attr('disabled', true);

            var isAccountCreation = $(this).attr("data-account-create");

            var selectVal = $(this).attr('data-name');
            var selectDate = $(this).attr('data-date');
            // Only continue if both values are filled in
            if (selectVal !== undefined && selectDate !== undefined) {
                var selectFriendly = $("#tnthproc option:selected").text();
                 // gather data
                var procArray = {};
                procArray["resourceType"] = "Procedure";
                procArray["performedDateTime"] = selectDate;

                if (isAccountCreation) {
                    if ($("#pastTreatmentsContainer tr[data-code='" + selectVal + "'][data-performedDateTime='" + selectDate + "']").length == 0) {
                        procArray["display"] = selectFriendly;
                        procArray["code"] = selectVal;
                        var content = "";
                        content += "<tr ";
                        for (var item in procArray) {
                            content +=  " data-" + item + "='" + procArray[item] + "'"
                        };
                        content += ">";
                        content += "<td>&#9679;</td><td>" + selectFriendly + "</td><td>" + selectDate + "</td><td><a class='btn btn-default btn-xs data-delete'>" + i18next.t("REMOVE") + "</a></td>";
                        content += "</tr>";
                        $("#pastTreatmentsContainer").append(content);
                        setTimeout(function() { $("#pastTreatmentsContainer").show(); }, 100);
                    };

                } else {
                    //remove any procedure on prostate or none treatment
                    //see main.js proceduresContent function that renders these as hidden fields
                    $("#userProcedures input[name='otherProcedures']").each(function() {
                        var code = $(this).attr("data-code"), procId = $(this).attr("data-id");
                        if (code == CANCER_TREATMENT_CODE) {
                            tnthAjax.deleteProc(procId);
                        };
                        if (code == NONE_TREATMENT_CODE) {
                            tnthAjax.deleteProc(procId);
                        };
                    });

                    var procID = [{ "code": selectVal, "display": selectFriendly, system: "http://snomed.info/sct" }];
                    procArray["subject"] = {"reference": "Patient/" + subjectId };
                    procArray["code"] = {"coding": procID};
                    tnthAjax.postProc(subjectId,procArray);

                    // Update the procedure list - we animate opacity to retain the
                    // width and height so lower content doesn't go up and down
                    $("#eventListLoad").show();

                    // Set a one second delay before getting updated list. Mostly to give user sense of progress/make it
                    // more obvious when the updated list loads
                    setTimeout(function(){
                        tnthAjax.getProc(subjectId,true);
                    },1500);

                    $("#pastTreatmentsContainer").hide();

                };

                $("select[id^='tnthproc']").val('');
                $("input[id^='tnthproc-value']").val('');
                $("input[id^='tnthproc-date']").val('');
                $("#procDay").val("");
                $("#procMonth").val("");
                $("#procYear").val("");
                // Clear submit button
                $("button[id^='tnthproc-submit']").addClass('disabled').attr({
                    "data-name": "",
                    "data-date": "",
                    "data-date-read": ""
                });

            };

            return false;
        });
    }
}); // $.fn.extend({

var procDateReg =  /(0[1-9]|1\d|2\d|3[01])/;
var procYearReg = /(19|20)\d{2}/;

$(document).ready(function() {

    // Options for datepicker - prevent future dates, no default
    $('.event-element .input-group.date').each(function(){
        $(this).datepicker({
            format: 'dd/mm/yyyy',
            endDate: "0d",
            startDate: "-10y",
            autoclose: true,
            forceParse: false
        });
    });

    // Trigger eventInput on submit button
    $("button[id^='tnthproc-submit']").eventInput();

    function isLeapYear(year)
    {
      return ((year % 4 == 0) && (year % 100 != 0)) || (year % 400 == 0);
    };

    function checkDate() {
        var d = $("#procDay").val(), m = $("#procMonth").val(), y = $("#procYear").val();
        if (!isNaN(parseInt(d))) {
            if (parseInt(d) > 0 && parseInt(d) < 10) d = "0" + d;
        };

        var dTest = procDateReg.test(d);
        var mTest = (m != "");
        var yTest = procYearReg.test(y);
        var errorText = "The procedure date must be valid and in required format.";
        var dgField = $("#procDateGroup");
        var deField = $("#procDateErrorContainer");
        var errorColor = "#a94442";
        var validColor = "#777";

        if (dTest && mTest && yTest) {

            var date = new Date(parseInt(y),parseInt(m)-1,parseInt(d));
            var today = new Date();
            //console.log("dy: " + date.getFullYear() + " y: " + parseInt(y) + " dm: " + (date.getMonth() + 1) + " m: " + parseInt(m) + " dd: " + date.getDate() + " d: " + parseInt(d))
            if (date.getFullYear() == parseInt(y) && ((date.getMonth() + 1) == parseInt(m)) && date.getDate() == parseInt(d)) {
                if (date.setHours(0,0,0,0) > today.setHours(0,0,0,0)) {
                    deField.text("The procedure date must be in the past.").css("color", errorColor);
                    return false;
                };
            } else {
                deField.text(errorText).css("color", errorColor);
                return false;
            };

            if (parseInt(m) === 2) { //month of February
                if (isLeapYear(parseInt(y))) {
                    if (parseInt(d) > 29)  {
                        deField.text(errorText).css("color", errorColor);
                        return false;
                    };
                } else {
                    if (parseInt(d) > 28) {
                        dgField.addClass("has-error");
                        deField.text(errorText).css("color", errorColor);
                        return false;
                    };
                };
                deField.text("").css("color", validColor);
                return true;
            } else {
                deField.text("").css("color", validColor)
                return true;
            };

        } else {
            return false;
        };
    };

    function setDate() {
        var isValid = checkDate();
        if (isValid) {
            var passedDate = dateFields.map(function(fn) {
            fd = $("#" + fn);
            if (fd.attr("type") == "text") return fd.val();
            else return fd.find("option:selected").val();
            }).join("/");
            //console.log("passedDate: " + passedDate);
            $("button[id^='tnthproc-submit']").attr('data-date-read',passedDate);
            dateFormatted = tnthDates.swap_mm_dd(passedDate);
            //console.log("formatted date: " + dateFormatted);
            $("button[id^='tnthproc-submit']").attr('data-date',dateFormatted);
        } else {
            $("button[id^='tnthproc-submit']").attr('data-date-read',"");
            $("button[id^='tnthproc-submit']").attr('data-date',"");
        };

        checkSubmit("button[id^='tnthproc-submit']");

    };

     // Add/remove disabled from submit button

    function checkSubmit(btnId) {
        if ($(btnId).attr("data-name") != "" && $(btnId).attr("data-date-read") != "") {
            // We trigger the click here. The button is actually hidden so user doesn't interact with it
            //$(btnId).removeClass('disabled').removeAttr('disabled').trigger("click");
            $(btnId).removeClass('disabled').removeAttr('disabled');
        } else {
            $(btnId).addClass('disabled').attr('disabled',true);
        };
    };

    // Update submit button when select changes
    $("select[id^='tnthproc']").on('change', function() {
        $("button[id^='tnthproc-submit']").attr("data-name", $(this).val());
        checkSubmit("button[id^='tnthproc-submit']");
    });
    // Update submit button when text input changes (single option)
    //datepicker field
    $("input[id^='tnthproc-value']").on('change', function() {
        $("button[id^='tnthproc-submit']").attr("data-name", $(this).val());
        checkSubmit("button[id^='tnthproc-submit']");
    });

    // When date changes, update submit button w/ both mm/dd/yyyy and yyyy-mm-dd
    var dateFields = ["procDay", "procMonth", "procYear"];

    dateFields.forEach(function(fn) {
        var triggerEvent = $("#" + fn).attr("type") == "text" ? "keyup": "change";
        $("#" + fn).on(triggerEvent, function() {
                setDate();
        });
    });

    $("input[id^='tnthproc-date']").on('change', function( event ) {
        var passedDate = $(this).val(); // eg "11/20/2016"
        //passedDate = tnthDates.swap_mm_dd(passedDate);
        //$("button[id^='tnthproc-submit']").attr('data-date-read',passedDate);
        var dateFormatted;
        // Change dates to YYYY-MM-DD
        //and make sure date is in dd/mm/yyyy format before reformat
        if (passedDate && passedDate != '' && /^(0[1-9]|[12][0-9]|3[01])[\/](0[1-9]|1[012])[\/]\d{4}$/.test(passedDate)) {
            $("button[id^='tnthproc-submit']").attr('data-date-read',passedDate);
            dateFormatted = tnthDates.swap_mm_dd(passedDate);
            //console.log("formatted date: " + dateFormatted);
            $("button[id^='tnthproc-submit']").attr('data-date',dateFormatted);
            checkSubmit("button[id^='tnthproc-submit']");
        }

    });

    /*** Delete functions ***/
    $('body').on('click', '.cancel-delete', function() {
        $(this).parents("div.popover").prev('a.confirm-delete').trigger('click');
    });

    $('body').on('click', '.data-delete', function() {
        $(this).closest("tr").remove();
    });
    // Need to attach delete functionality to body b/c section gets reloaded
    $("body").on('click', ".btn-delete", function() {
        var procId = $(this).parents('tr').attr('data-id');
        // Remove from list
        $(this).parents('tr').fadeOut('slow', function(){
            $(this).remove();
            // If there's no events left, add status msg back in
            if ($('#eventListtnthproc tr').length == 0) {
                $("body").find("#userProcedures").html("<p id='noEvents' style='margin: 0.5em 0 0 1em'><em>You haven't entered any treatments yet.</em></p>").animate({opacity: 1});
            };
        });
        // Post delete to server
        tnthAjax.deleteProc(procId);
        return false;
    });

});
