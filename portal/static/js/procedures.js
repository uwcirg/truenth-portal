$.fn.extend({
    // Special type of select question - passes two values - the answer from
    // the select plus an associated date from a separate input
    eventInput: function(settings) {
        $(this).on("click", function() {

            // First disable button to prevent double-clicks
            $(this).attr('disabled', true);

            var selectVal = $(this).attr('data-name');
            var selectDate = $(this).attr('data-date');
            // Only continue if both values are filled in
            if (selectVal !== undefined && selectDate !== undefined) {

                // Submit the data
                var procArray = {};
                var selectFriendly = $("#tnthproc option:selected").text();
                var procID = [{ "code": selectVal, "display": selectFriendly,
                    system: "http://snomed.info/sct" }];
                procArray["resourceType"] = "Procedure";
                procArray["subject"] = {"reference": "Patient/" + subjectId };
                procArray["code"] = {"coding": procID};
                procArray["performedDateTime"] = selectDate;
                tnthAjax.postProc(subjectId,procArray);

                // Update the procedure list - we animate opacity to retain the
                // width and height so lower content doesn't go up and down
                $("#userProcedures").animate({opacity: 0}, function() {
                    $(this).html(eventLoading).css('opacity',1);
                    // Clear the inputs
                    $("select[id^='tnthproc']").val('');
                    $("input[id^='tnthproc-value']").val('');
                    $("input[id^='tnthproc-date']").val('');
                    // Clear submit button
                    $("button[id^='tnthproc-submit']").addClass('disabled').attr({
                        "data-name": "",
                        "data-date": "",
                        "data-date-read": ""
                    });
                    // Set a one second delay before getting updated list. Mostly to give user sense of progress/make it
                    // more obvious when the updated list loads
                    setTimeout(function(){
                        tnthAjax.getProc(subjectId,true);
                    },1000);

                });
            }

            return false;
        });
    }
}); // $.fn.extend({

var eventLoading = '<div style="margin: 1em" id="eventListLoad"><i class="fa fa-spinner fa-spin fa-2x loading-message"></i></div>';

$(document).ready(function() {

    // Options for datepicker - prevent future dates, no default
    $('.event-element .input-group.date').each(function(){
        $(this).datepicker({
            dateFormat: 'd/M/yyyy',
            endDate: "0d",
            startDate: "-10y",
            autoclose: true
        });
    });

    // Trigger eventInput on submit button
    $("button[id^='tnthproc-submit']").eventInput();

    // Add/remove disabled from submit button
    function checkSubmit(btnId) {

        if ($(btnId).attr("data-name") != "" && $(btnId).attr("data-date-read") != "") {
            // We trigger the click here. The button is actually hidden so user doesn't interact with it
            // TODO - Remove the button completely and store the updated values elsewhere
            $(btnId).removeClass('disabled').removeAttr('disabled').trigger("click");
        } else {
            $(btnId).addClass('disabled').attr('disabled',true);
        }
    }

    // Update submit button when select changes
    $("select[id^='tnthproc']").on('change', function() {
        $("button[id^='tnthproc-submit']").attr("data-name", $(this).val());
        checkSubmit("button[id^='tnthproc-submit']");
    });
    // Update submit button when text input changes (single option)
    $("input[id^='tnthproc-value']").on('change', function() {
        $("button[id^='tnthproc-submit']").attr("data-name", $(this).val());
        checkSubmit("button[id^='tnthproc-submit']");
    });
    // When date changes, update submit button w/ both mm/dd/yyyy and yyyy-mm-dd
    $("input[id^='tnthproc-date']").on('change', function( event ) {
        var passedDate = $(this).val(); // eg "11/20/2016"
        passedDate = tnthDates.swap_mm_dd(passedDate);
        $("button[id^='tnthproc-submit']").attr('data-date-read',passedDate);
        var dateFormatted;
        // Change dates to YYYY-MM-DD
        //and make sure date is in dd/mm/yyyy format before reformat
        if (passedDate && passedDate != '' && /^(0[1-9]|[12][0-9]|3[01])[\/](0[1-9]|1[012])[\/]\d{4}$/.test(passedDate)) {
            dateFormatted = tnthDates.swap_mm_dd(passedDate);
            //console.log("formatted date: " + dateFormatted);
            $("button[id^='tnthproc-submit']").attr('data-date',dateFormatted);
            checkSubmit("button[id^='tnthproc-submit']");
        };
        
    });

    /*** Delete functions ***/
    $('body').on('click', '.cancel-delete', function() {
        $(this).parents("div.popover").prev('a.confirm-delete').trigger('click');
    });
    // Need to attach delete functionality to body b/c section gets reloaded
    $("body").on('click', ".btn-delete", function() {
        var procId = $(this).parents('li').attr('data-id');
        // Remove from list
        $(this).parents('li').fadeOut('slow', function(){
            $(this).remove();
            // If there's no events left, add status msg back in
            if ($('#eventListtnthproc li').length == 0) {
                $("body").find("#userProcedures").html("<p id='noEvents' style='margin: 0.5em 0 0 1em'><em>You haven't entered any treatments yet.</em></p>").animate({opacity: 1});
            }
        });
        // Post delete to server
        tnthAjax.deleteProc(procId);
        return false;
    });

});
