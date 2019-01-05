import OrgTool from "./modules/OrgTool";
$(function() {
    var OT = new OrgTool(); /*global OrgTool $*/
    OT.init(function() {
        OT.populateUI();
        $("#fillOrgs legend, #fillOrgs .org-label").each(function() {
            var orgId = $(this).attr("orgid") ||  $(this).attr("id").split("-")[2];
            $(this).append(`<span class='sub-text'>&nbsp;&nbsp;${orgId}</span>`);
            $(this).append(`<a href='/api/organization/${orgId}' target='_blank' class='json-link'>View JSON</a>`);
        });
    });
});

