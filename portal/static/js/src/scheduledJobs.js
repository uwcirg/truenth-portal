
$(document).ready(function() {
    $("#scheduledJobsList .btn-toggle-job").on("click", function(event) { /* global $ */
        event.stopPropagation();
        var jobId = $(this).attr("data-jobid");
        if (!jobId) {
            return;
        }
        var current_job = "#job_"+jobId;
        var current_text = "#activeText_" + jobId;
        var current_icon = "#activeIcon_" + jobId;
        var current_status = "#lastStatus_" + jobId;
        var jobData = {active: ($(current_text).text() !== "Active")};
        $(current_job).children().prop("disabled",true);
        $(current_job).fadeTo("fast",.6);
        $.ajax ({
            type: "PUT",
            url: "/api/scheduled_job/" + jobId,
            contentType: "application/json; charset=utf-8",
            dataType: "json",
            data: JSON.stringify(jobData)
        }).done(function(data) {
            if (data) {
                if (data["active"]) {
                    $(current_text).text("Active");
                    $(current_text).removeClass("text-danger");
                    $(current_icon).removeClass("fa fa-toggle-off");
                    $(current_text).addClass("text-info");
                    $(current_icon).addClass("fa fa-toggle-on");
                } else {
                    $(current_text).text("Inactive");
                    $(current_text).removeClass("text-info");
                    $(current_icon).removeClass("fa fa-toggle-on");
                    $(current_text).addClass("text-danger");
                    $(current_icon).addClass("fa fa-toggle-off");
                }
                $(current_job).fadeTo("fast",1);
                $(current_job).children().prop("disabled",false);
            } else {
                $(current_status).text("No response received");
                $(current_status).removeClass("text-info");
                $(current_status).addClass("text-danger");
            }
        }).fail(function(xhr) {
            console.log("response Text: " + xhr.responseText);
            console.log("response status: " +  xhr.status);
            $(current_status).text(xhr.status + ": " + xhr.responseText);
            $(current_status).removeClass("text-info");
            $(current_status).addClass("text-danger");
        });
    });
    $("#scheduledJobsList .btn-run-job").on("click", function(event) {
        event.stopPropagation();
        var jobId = $(this).attr("data-jobid");
        if (!jobId) {
            return;
        }
        var current_job = "#job_"+jobId;
        var current_status = "#lastStatus_" + jobId;
        var current_runtime = "#lastRuntime_" + jobId;
        $(current_job).children().prop("disabled",true);
        $(current_job).fadeTo("fast",.6);
        $.ajax ({
            type: "POST",
            url: "/api/scheduled_job/" + jobId + "/trigger",
            contentType: "application/json; charset=utf-8",
            dataType: "json"
        }).done(function(data) {
            if (data) {
                $(current_status).text(data["message"]);
                $(current_runtime).text(data["runtime"]);
                $(current_job).fadeTo("fast",1);
                $(current_job).children().prop("disabled",false);
            } else {
                $(current_status).text("No response received");
                $(current_status).removeClass("text-info");
                $(current_status).addClass("text-danger");
            }
        }).fail(function(xhr) { /*eslint no-console: off*/
            console.log("response Text: " + xhr.responseText);
            console.log("response status: " +  xhr.status);
            $(current_status).text(xhr.status + ": " + xhr.responseText);
            $(current_status).removeClass("text-info");
            $(current_status).addClass("text-danger");
        });
    });
});
