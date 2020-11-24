
import tnthDates from "./modules/TnthDate";
import TestJson from "./data/common/MainStudyQuestionnaireTestData.json";

$(document).on("ready", function() {
    $(".button-container").each(function() {
        $(this).prepend('<div class="loading-message-indicator"><i class="fa fa-spinner fa-spin fa-2x"></i></div>');
    });
    $(".btn-tnth-primary").on("click", function(event) {
        if ($(this).hasClass("disabled")) {
            return false;
        }
        var link = $(this).attr("href");
        if (link) {
            event.preventDefault();
            $(this).hide();
            $(this).prev(".loading-message-indicator").show();
            setTimeout(function() {
                window.location=link;
            }, 300);
        }
    });
    $("body").addClass("portal");

    /*
     * enable debugging: key combo: Crtl + Shift + "d"
     */
    document.addEventListener("keydown", event => {
        if (event.ctrlKey && 
            event.shiftKey &&
            event.key.toLowerCase() === "d") {
            $("#developmentToolsContainer").removeClass("hide");
            return false;
        }
        
    });
    /* 
     * Click event for the test button - will submit fake data for the main study questionnaires for the subject
     * NOTE: button is activated via key combo Crtl + Shift + "d"
     */
    $("#btnTestData").on("click", () => {
        $.ajax({
            type: "GET",
            url: "/api/me"
        }).done(function(data) {
            if (!data.id) return;
            let entry = TestJson.entry;
            let reference = `${location.origin}/api/demographics/${data.id}`;
            let semaphors = entry.length;
            let errorMessage = "";
            let requestsCompleted = () => {
                if (semaphors == 0) {
                    $("#btnTestData").removeClass("disabled").attr("disabled", false);
                    $("#developmentToolsContainer .loader").addClass("hide");
                    if (!errorMessage) {
                        location.reload();
                        return;
                    }
                    $("#developmentToolsContainer .error").html("error occurred processing data, see console for detail.")
                }
            };
            let beforeRequests = () => {
                $("#btnTestData").addClass("disabled").attr("disabled", true);
                $("#developmentToolsContainer .loader").removeClass("hide");
                $("#developmentToolsContainer .error").html("");
            };
           
            beforeRequests();
            entry.forEach((item, index) => {
                let postData = item;
                /*
                * set authored date to current date/time GMT
                */
                postData.authored = tnthDates.getTodayDateObj().gmtDate;
                /*
                 *  make sure any reference should reference the current subject account
                 */
                postData.author.reference = reference;
                postData.source.reference = reference;
                postData.subject.reference = reference;
                $.ajax({
                    type: "POST",
                    url: `/api/patient/${data.id}/assessment`,
                    data: JSON.stringify(postData),
                    contentType: "application/json",
                    dataType: "json"
                }).done(() => {
                    semaphors--;
                    requestsCompleted(true);
                }).fail((e) => {
                    console.log("test data post failed ", e);
                    errorMessage = e;
                    semaphors--;
                    requestsCompleted();
                });
            });
        });
    });

});
