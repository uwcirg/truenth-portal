    $(document).ready(function() {

        var eventLoading = '<div style="margin: 1em" id="eventListLoad"><i class="fa fa-spinner fa-spin fa-2x loading-message"></i></div>';
        // Options for datepicker - prevent future dates, no default
        $('.event-element input.datep').each(function(){
            $(this).datepicker({
                dateFormat: 'mm/dd/yy',
                changeMonth: true,
                changeYear: true,
                maxDate: "0"
            });
        });

        // Post to server - uses on click for "Add Event" button
        $("button[id^='1494-submit']").eventInput({
            page_id: 489        });

        // Add/remove disabled from submit button
        function checkSubmit(btnId) {
            if ($(btnId).attr("data-name") != "" && $(btnId).attr("data-date-read") != "") {
                $(btnId).removeClass('disabled').removeAttr('disabled').addClass('pulse');
            } else {
                $(btnId).addClass('disabled').attr('disabled',true).removeClass('pulse');
            }
        }

        // Special type of select question - passes two values - the answer from
        // the select plus an associated date from a separate input
        eventInput: function(settings) {
            $(this).on("click", function() {
                var selectVal = $(this).attr('data-name');
                var selectDate = $(this).attr('data-date');
                // Only post if value and date have been chosen
                if (selectVal !== undefined && selectDate !== undefined) {
/**
TODO
                  $.ajaxAnswer(this.name,     // question
                        "",    // option - blank
                        selectDate, // date passed to state field
                        "", // text - blank
                        settings.page_id,
                        selectVal); // answer passed to value
*/
                }
                return false;
            });
        },

        // Update submit button when select changes
        $("select[id^='1494']").on('change', function() {
            $("button[id^='1494-submit']").attr("data-name", $(this).val());
            checkSubmit("button[id^='1494-submit']");
        });
        // Update submit button when text input changes (single option)
        $("input[id^='1494-value']").on('change', function() {
            $("button[id^='1494-submit']").attr("data-name", $(this).val());
            checkSubmit("button[id^='1494-submit']");
        });
        // When date changes, update submit button w/ both mm/dd/yyyy and yyyy-mm-dd
        $("input[id^='1494-date']").on('change', function( event ) {
            var passedDate = $(this).val();
            $("button[id^='1494-submit']").attr('data-date-read',passedDate);
            var dateFormatted;
            // Change dates to YYYY-MM-DD
            if (passedDate && passedDate != '') {
                dateFormatted = cproDates.changeFormat(passedDate);
            }
            $("button[id^='1494-submit']").attr('data-date',dateFormatted);
            checkSubmit("button[id^='1494-submit']");
        });

        // Add Event submit button - click posts to server (in cpro.jquery) and here we add
        // it to the list of previous event
        // Note - this and cpro.jquery both look for on click. could combine.
        $("button[id^='1494-submit']").on("click", function(event){
            // First disable button to prevent double-clicks
            $(this).attr('disabled', true);
            var eventName = $(this).attr('data-name');
            var eventDate = $(this).attr('data-date-read');
            if (eventName != "" && eventDate != "") {
                // First fadeOut the #eventList - we animate opacity to retain the
                // width and height so lower content doesn't go up and down
                $("#eventList1494").animate({opacity: 0}, function() {
                    // Hide the #noEvents text (if showing)
                    $("#noEvents").hide();
                    $(this).html(eventLoading).css('opacity',1);
                    // Clear the inputs
                    $("select[id^='1494']").val('');
                    $("input[id^='1494-value']").val('');
                    $("input[id^='1494-date']").val('');
                    // Clear submit button
                    $("button[id^='1494-submit']").addClass('disabled').removeClass('pulse').attr({
                        "data-name": "",                        "data-date": "",
                        "data-date-read": ""
                    });
                    // Since we need answer ID from server for delete, reload the eventList
                    $("#eventList1494").load("489 #eventList1494  > *", function(){
                        // Popover needs to be called again here b/c of element load
                        $("[rel=popover-confirm]").popover({
                            trigger: 'click',
                            placement: 'right',
                            html: true
                        });
                        // Grab most recent event on load to highlight new entries on reload
                        var mostRecentId = 11891;
                        // Add a "new" icon to ones that were created via ajax submit
                        $("#eventList1494 li").each(function() {
                            var eventId = $(this).attr('data-id');
                            if (eventId > mostRecentId) {
                                $(this).append("&nbsp; <span class='text-success'><i class='fa fa-check-square-o'></i> <em>Added!</em></span>");
                            }
                        });
                        // Fade in the eventList with opacity
                        $("#eventList1494").animate({opacity: 1});
                    });
                });
            }
        });

        /*** Delete functions ***/
            // Main delete function handled in cpro.js - using rel="popover-confirm"
        $('body').on('click', '.cancel-delete', function() {
            $(this).parents("div.popover").prev('a.confirm-delete').trigger('click');
        });
        // Need to attach delete functionality to body b/c section gets reloaded
        $("body").on('click', ".btn-delete", function() {
            // Get ID for this answer
            var answerId = $(this).parents('li').attr('data-id');
            // Remove from list
            $(this).parents('li').fadeOut('slow', function(){
                $(this).remove();
                // If there's no events left, add status msg back in
                if ($('#eventList1494 li').length == 0) {
                    $('#eventList1494').prepend("<p id='noEvents' style='margin-top: 8px'><em>You haven't added any procedures.</em></p>");
                }
            });
            // Post delete to server
            $.post(appRoot + controller + "/deleteAnswer.json", {
                "data[Answer][id]" : answerId,
                "data[AppController][AppController_id]" : acidValue
            }, "json");
            return false;
        });

    });
