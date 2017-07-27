//a workaround for wrapper not finished loading before the content displays, the finish loading of wrapper hides the loader
DELAY_LOADING = true;

function AdminTool (userId) {
  this.requestsCounter = 0;
  this.userId = userId;
  this.userOrgs = [];
  this.initUserList = [];
  OrgTool.call(this);
};

/*
* extends OrgTool class
* see OT class definition in main.js should modularize it in the future so it can be instantiated/called safely
*
*/
AdminTool.prototype = Object.create(OrgTool.prototype);
AdminTool.prototype.fadeLoader = function() {
  DELAY_LOADING = false;
  setTimeout('$("#loadingIndicator").fadeOut();', 300);
  this.setLoadingMessageVis("hide");
};
AdminTool.prototype.setLoadingMessageVis = function(vis) {
  switch(vis) {
    case "hide":
      $("#patientListLoadingMessage").fadeOut();
      break;
    case "show":
      $("#patientListLoadingMessage .loading-message-indicator").show();
      $("#patientListLoadingMessage").fadeIn();
      break;
  };
};
AdminTool.prototype.getData = function(userString, callback) {
    var self = this;
    $.ajax ({
        type: "GET",
        url: '/api/consent-assessment-status',
        contentType: "application/json; charset=utf-8",
        data: userString,
        cache: false,
        timeout: 25000,
        dataType: 'json'
    }).done(function(data) {
        if (data.status) {
          var arrData = [];
          data.status.forEach(function(status) {
              var c = status.consents;
              var a = "", s = "", prevItem = {};
              if (c) {
              c.forEach(function(item) {
                  if (!item.consent.deleted && (!prevItem.consent_signed || (prevItem.assessment_status != item.assessment_status)
                      || (String(prevItem.consent_signed).substring(0, 10) != String(item.consent.signed).substring(0, 10)))) {
                      if (!(/null/.test(item.consent.agreement_url))) {
                        var cl = "";
                        var sd = tnthDates.formatDateString(item.consent.signed);
                        var status = item.assessment_status;
                        if (!item.consent.send_reminders) status = "withdrawn";
                        switch(String(status).toLowerCase()) {
                            case "completed":
                              cl = "text-success";
                              break;
                            case "withdrawn":
                              cl = "text-muted";
                              break;
                            case "due":
                              cl = "text-warning";
                              break;
                            case "overdue":
                              cl = "text-danger";
                              break;
                        };
                        a += (a != "" ? "<br/>" : "") + "<span class='" + cl  + " small-text' style='text-transform: capitalize'>" + status + "</span>";
                        s += (s != "" ? "<br/>" : "") + sd;
                        prevItem.assessment_status = item.assessment_status;
                        prevItem.consent_signed = item.consent.signed;
                      };
                    };
                });
            };
            arrData.push({
              "id": status.user_id,
              "data": {
              "status": a
              }
            });
          });

          if (arrData.length > 0) {
              arrData.forEach(function(d) {
                $("#adminTable").bootstrapTable('updateByUniqueId', { id: d.id, row: d.data});
              });
          };
        };
        self.requestsCounter -= 1;
        if(self.requestsCounter == 0) {
          self.requestsCounter = 0;
          self.fadeLoader();
          if (callback) callback.call(self);
        };
    }).fail(function(xhr) {
        //console.log("request failed.");
        $("#admin-table-error-message").text("Server error occurred updating row data.  Server error code: " + xhr.status);
        self.fadeLoader();
        self.setLoadingMessageVis("hide");
    });
};
AdminTool.prototype.loadData = function(list, callback) {
    var self = this;
    self.requestsCounter = list.length;
    list.forEach(function(us) {
        try {
          setTimeout(function() { self.getData(us, function() { callback.call(self); }); }, 0);
        } catch(ex) {
          //console.log("Error request: " + ex.message);
          self.fadeLoader();
        };
    });
};
AdminTool.prototype.updateData = function() {
  var arrUsers = this.getUserIdArray();
  var self = this;
  if (arrUsers.length > 0) {
    $("#admin-table-error-message").text("");
    loader(true);
    self.loadData(arrUsers, this.getRestData);
  } else {
    self.fadeLoader();
  };
};

/*
 *
 *  load the rest of data asynchronously
 *
 */

AdminTool.prototype.getRestData = function() {
   if (__patients_list.length > 0) {
    var self = this;
    //get rest of patients, don't need to load data for id whose data has been updated
    __patients_list = __patients_list.filter(function(id) {
      return !this.inArray(id, this.initUserList)
    }, self);
    var arrList = this.getUserIdArray(__patients_list);
    this.setLoadingMessageVis("show");
    self.loadData(this.getUserIdArray(__patients_list), function() { this.setLoadingMessageVis("hide");});
  };
}
AdminTool.prototype.getInitUserList = function() {
   var _userIds = [];
   $("#adminTable tr[data-uniqueid]").each(function() {
        var id = $(this).attr("data-uniqueid");
        if (!isNaN(id)) {
          _userIds.push(id);
        };
   });
   this.initUserList = _userIds;
   return _userIds;
}
AdminTool.prototype.getUserIdArray = function(_userIds) {
  var us = "", ct = 0, arrUsers = [];
  if (!_userIds) {
     _userIds = this.getInitUserList();
  };
  for (var index = 0; index < _userIds.length; index++, ct++) {
     us += (us != ""?"&":"") + "user_id=" + _userIds[index];
     if (index == (_userIds.length - 1)) {
       arrUsers.push(us);
     } else if (ct >= 15) {
        arrUsers.push(us);
        us = "";
        ct = 0;
     };
  };

  return arrUsers;
};
AdminTool.prototype.setUserOrgs = function() {
  var self = this;
  $.ajax ({
          type: "GET",
          url: '/api/demographics/'+this.userId,
          async: false
  }).done(function(data) {
    if (data && data.careProvider) {
      $.each(data.careProvider,function(i,val){
          var orgID = val.reference.split("/").pop();
          self.userOrgs.push(orgID);
          if (orgID == "0") $("#createUserLink").attr("disabled", true);
      });
    if (self.userOrgs.length == 0) $("#createUserLink").attr("disabled", true);
    };
  }).fail(function() {

  });
};
AdminTool.prototype.getUserOrgs = function() {
  if (this.userOrgs.length == 0) this.setUserOrgs(this.userId);
  return this.userOrgs;
};
AdminTool.prototype.initOrgsList = function(request_org_list) {
    //set user orgs
    var self = this;
    self.setUserOrgs();
    var iterated = /org_list/.test(location.href);

    var noPatientData = $("#admin-table-body").find("tr.no-records-found").length > 0;

    $.ajax ({
        type: "GET",
        url: '/api/organization'
    }).done(function(data) {
        self.populateOrgsList(data.entry);
        self.populateUI();
        if (!noPatientData) {
            var hbOrgs = self.getHereBelowOrgs();
	          self.filterOrgs(hbOrgs);
        };

        if ($("#adminTable .study-id-field").length > 0) {
          AT.drawStudyIDLabel(AT.getUserTopLevelParentOrgs(AT.getUserOrgs()), true);
        };

        $("#dataDownloadModal").on('shown.bs.modal', function () {
              var parentOrgList = AT.getUserTopLevelParentOrgs(AT.getUserOrgs());
              if (parentOrgList && parentOrgList.length > 0) {
                 var instrumentList = self.getInstrumentList();
                 var instrumentItems = [];
                 parentOrgList.forEach(function(o) {
                    var il = instrumentList[o];
                    if (il) {
                      il.forEach(function(n) {
                        instrumentItems.push(n);
                      });
                    };
                 });
                 if (instrumentItems.length > 0) {
                    $(".instrument-container").hide();
                    instrumentItems.forEach(function(item) {
                      $("#" + item + "_container").show();
                    });
                 };
              };
              $("#patientsInstrumentList").addClass("ready");
        });
        var ofields = $("#userOrgs input[name='organization']");
        ofields.each(function() {
            if ((AT.getHereBelowOrgs()).length == 1 || (iterated && request_org_list && request_org_list[$(this).val()])) $(this).prop("checked", true);
            $(this).on("click touchstart", function(e) {
                e.stopPropagation();
                var orgsList = [];
                $("#userOrgs input[name='organization']").each(function() {
                    if ($(this).is(":checked")) orgsList.push($(this).val());
                });
                if (orgsList.length > 0) {
                  location.replace("/patients/?org_list=" + orgsList.join(","));
                } else location.replace("/patients");
            });
        });
        if (ofields.length > 0) {
          $("#org-menu").append("<hr><div id='orglist-footer-container'><label><input type='checkbox' id='orglist-selectall-ckbox'>&nbsp;<span class='text-muted'>Select All</span></label>&nbsp;&nbsp;&nbsp;<label><input type='checkbox' id='orglist-clearall-ckbox'>&nbsp;<span class='text-muted'>Clear All</span></label>&nbsp;&nbsp;&nbsp;<label><input type='checkbox' id='orglist-close-ckbox'>&nbsp;<span class='text-muted'>Close</span></label></div>");
          $("#orglist-selectall-ckbox").on("click touchstart", function(e) {
              e.stopPropagation();
              var orgsList = [];
              $("#userOrgs input[name='organization']").each(function() {
                  if ($(this).is(":visible")) {
                    $(this).prop("checked", true);
                    orgsList.push($(this).val());
                  };
              });
              $("#orglist-clearall-ckbox").prop("checked", false);
              location.replace("/patients/?org_list=" + orgsList.join(","));
          });
          $("#orglist-clearall-ckbox").on("click touchstart", function(e) {
              e.stopPropagation();
              $("#userOrgs input[name='organization']").each(function() {
                  $(this).prop("checked", false);
              });
          });
          $("#orglist-close-ckbox").on("click touchstart", function(e) {
              e.stopPropagation();
              $("#orglistSelector").trigger("click");
              return false;
          });
        };

    }).fail(function() {
        //console.log("Problem retrieving data from server.");
        $("#org-menu").append("<span class='indent text-danger'>Error occurred retrieving data from server.</span>");
    });

    //orglist-dropdown
    $('#orglist-dropdown').on('click touchstart', function () {
        setTimeout('__setOrgsMenuHeight(100); __clearFilterButtons();', 10);
    });

    if (noPatientData) $("#patientListExportDataContainer").hide();
};
AdminTool.prototype.getInstrumentList = function() {
  return {
    //CRV
    '10000': ['epic26', 'eproms_add', 'comorb'],
    //IRONMAN
    '20000': ['eortc', 'ironmisc', 'factfpsi', 'epic26', 'prems', 'irondemog']
  };
};
__setOrgsMenuHeight = function(padding) {
  if (!padding) padding = 100;
  var h = parseInt($("#fillOrgs").height());
  if (!isNaN(h) && h > 0) {
    $("#org-menu").height(h + padding);
    if ($("div.admin-table").height() < $("#org-menu").height()) {
        setTimeout('$("div.admin-table").height($("#org-menu").height() + ' + padding + ');', 0);
    };
  };
};
__clearFilterButtons = function() {
  $("#orglist-close-ckbox, #orglist-clearall-ckbox, #orglist-selectall-ckbox").prop("checked", false);
};


