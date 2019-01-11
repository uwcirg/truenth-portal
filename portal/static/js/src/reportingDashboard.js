import {getExportFileName} from "./modules/Utility.js"; /*global $*/
(function() {
    /*
    * initiate bootstrapTable for all stats table
    */
    $("#orgStatsTable").bootstrapTable({
        exportOptions: {
            fileName: getExportFileName("OrganizationList_")
        }
    });
    $("#usageStatsTable").bootstrapTable({
        exportOptions: {
            fileName: getExportFileName("UsageStatsList_")
        }
    });
    $("#userRoleStatsTable").bootstrapTable({
        exportOptions: {
            fileName: getExportFileName("UserByRoleStatsList_")
        }
    });
    $("#userIntervStatsTable").bootstrapTable({
        exportOptions: {
            fileName: getExportFileName("UserByInterventionStatsList_")
        }
    });
    $("#userPatientReportStatsTable").bootstrapTable({
        exportOptions: {
            fileName: getExportFileName("UserByPatientReportStatsList_")
        }
    });
    $("#userIntervAccessStatsTable").bootstrapTable({
        exportOptions: {
            fileName: getExportFileName("UserByInterventionAccessStatsList_")
        }
    });

    $("document").ready(function() {
        /*
        * the class active will allow content related to the selected tab/item to show
        * the related item is found based on the data-id attributed attached to each anchor element
        */
        $("ul.nav li").each(function() {
            $(this).on("click",function() {
                $("ul.nav li").removeClass("active");
                $(this).addClass("active");
                var containerID = $(this).find("a").attr("data-id");
                if (containerID) {
                    $(".stats-container").removeClass("active");
                    $("#"+containerID+"_container").addClass("active");
                }
            });
        });
        /*
        * add placeholder text for select filter control
        */
        (function() {
            function addFilterPlaceHolders() {
                $(".stats-table .filterControl select option[value='']").text("Select");
            }
            $(".stats-table").on("reset-view.bs.table", function() {
                addFilterPlaceHolders();
            });
            addFilterPlaceHolders();
        })();
    });
})();
