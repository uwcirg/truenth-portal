/*
 * communications.js JS for communications page used by Admin staff
 */
/*
 * initialize communication modal
 */
/*
global $
*/
$(document).ready(function() {
    $("#commModal").modal({
        show: false
    });
    $(".btn-communication").on("click", function(e) {
        e.stopImmediatePropagation();
        previewComm($(this).attr("data-communication-id"));
    });
});

function previewComm(commId) {
    if (!commId) {
        return false;
    }
    $.ajax ({
        type: "GET",
        url: "/communicate/preview/" + commId,
        contentType: "application/json; charset=utf-8",
        dataType: "json",
        async: false
    }).done(function(data) {
        //no need for translation, as view by admin staff only
        if (!data) {
            $("#commMessage").html("No data returned");
            return false;
        }
        $("#commRecipients").html(data["recipients"]||"Not available");
        $("#commSubject").html(data.subject || "Not available");
        $("#commBody").html(data.body||"Not available");
        /*
        * prevent links and buttons in email body from being clickable
        */
        $("#commBody a").each(function() {
            $(this).on("click", function(e) {
                e.preventDefault();
                return false;
            });
        });
        /*
        * remove inline style in email body
        * style here is already applied via css
        */
        $("#commBody style").remove();
        $("#commModal").modal("show");
    }).fail(function(xhr) {
        $("#commMessage").html("Unable to retrieve content <br/>" + "status " + xhr.status + "<br/>" + xhr.responseText);
    });
}

