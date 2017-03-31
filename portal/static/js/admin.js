//a workaround for wrapper not finished loading before the content displays, the finish loading of wrapper hides the loader
DELAY_LOADING = true;

function AdminTool (userId) {
  this.requestsCounter = 0;
  this.userId = userId;
  this.userOrgs = [];
  this.here_below_orgs = [];
};

/*
*
* see OT class definition in main.js should modularize it in the future so it can be instantiated/called safely
*
*/

AdminTool.prototype.fadeLoader = function() {
  DELAY_LOADING = false;
  setTimeout('$("#loadingIndicator").fadeOut();', 300);
};

AdminTool.prototype.getData = function(userString) {
    var self = this;
    $.ajax ({
        type: "GET",
        url: '/api/consent-assessment-status',
        contentType: "application/json; charset=utf-8",
        data: userString,
        timeout: 20000,
        dataType: 'json'
    }).done(function(data) {
       // console.log(data);
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
                        var sd = item.consent.signed? (item.consent.signed).substring(0, 10) : "";
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
                        s += (s != "" ? "<br/>" : "") + "<span class='small-text'>" + (sd ? (sd.substr(5).replace(/\-/g, "/") + "/" + sd.substring(0, 4)) : "") + "</span>";
                        prevItem.assessment_status = item.assessment_status;
                        prevItem.consent_signed = item.consent.signed;
                      };
                    };
                });
            };
              //console.log("user id: " + status.user_id)
              arrData.push({
                "id": status.user_id,
                "data": {
                "status": a,
                "consentdate": s
                }
              });
          });

          if (arrData.length > 0) {
            //console.log(arrData)
            arrData.forEach(function(d) {
               var row = $("#id_row_" + d.id);
               if (row.length > 0) {
                  var rindex = row.attr("data-index");
                  var statusField = row.children(".status-field");
                  var cdField = row.children(".consentdate-field");
                 //console.log("status: " + statusField.length + " cdField: " + cdField.length);
                 if (d.data.status) statusField.html(d.data.status);
                 if (d.data.consentdate) cdField.html(d.data.consentdate);

                 //card view
                 var cvf = row.find(".card-view");
                 cvf.each(function() {
                    var ctf = $(this).find(".title");
                    if ((/consent date/gi).test(ctf.text())) {
                      ctf.next().html(d.data.consentdate);
                    };
                 });

               };
            });

          };
        };
        //console.log("consent updated successfully.");
        self.requestsCounter -= 1;
        if(self.requestsCounter == 0) {
          self.fadeLoader();
        };
    }).fail(function(xhr) {
        //console.log("request failed.");
        $("#admin-table-error-message").text("Server error occurred updating row data.  Server error code: " + xhr.status);
        self.fadeLoader();
    });
  };

AdminTool.prototype.getUserIdArray = function() {
  var us = "", _userIds = [], ct = 0, arrUsers = [];

  $("#adminTable tr[data-uniqueid]").each(function() {
      var id = $(this).attr("data-uniqueid");
      if (!isNaN(id)) {
        _userIds.push(id);
      };
  });
  for (var index = 0; index < _userIds.length; index++, ct++) {
     us += (us != ""?"&":"") + "user_id=" + _userIds[index];
     if (index == (_userIds.length - 1)) {
       arrUsers.push(us);
     } else if (ct >= 10) {
        arrUsers.push(us);
        us = "";
        ct = 0;
     };
  };

  return arrUsers;
};
AdminTool.prototype.updateData = function() {
  var arrUsers = this.getUserIdArray();
  var self = this;
  if (arrUsers.length > 0) {
    self.requestsCounter = arrUsers.length;
    $("#admin-table-error-message").text("");
    loader(true);
    arrUsers.forEach(function(us) {
        try {
         self.getData(us);
        } catch(ex) {
          //console.log("Error request: " + ex.message);
          self.fadeLoader();
        };
    });
  } else {
    self.fadeLoader();
  };
};
AdminTool.prototype.getMainOrgList = function() {
    return OT.getOrgsList();
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
__getChildOrgs = function(orgs, ref) {
    var mainOrgsList = ref.getMainOrgList();
    if (!orgs || (orgs.length == 0)) {
      return ref.here_below_orgs;
    } else {
      var childOrgs = [];
      orgs.forEach(function(org) {
          var o = mainOrgsList[org.id];
          if (o) {
            if (ref) ref.here_below_orgs.push(org.id);
            var c  = o.children ? o.children : null;
            if (c && c.length > 0) {
                c.forEach(function(i) {
                  childOrgs.push(i);
                });
            };
          };
      });
      return __getChildOrgs(childOrgs, ref);
    };
};
AdminTool.prototype.getHereBelowOrgs = function() {
  var userOrgs = this.userOrgs, mainOrgsList = OT.getOrgsList(), self = this;
  userOrgs.forEach(function(orgId) {
      self.here_below_orgs.push(orgId);
      var co = mainOrgsList[orgId];
      __getChildOrgs((co && co.children ? co.children : null), self);
  });
};
AdminTool.prototype.inArray = function( n, array) {
  if (n && array && Array.isArray(array)) {
    var found = false;
    for (var index = 0; !found && index < array.length; index++) {
        if (array[index] == n) found = true;
    };
    return found;
  } else return false;
};
AdminTool.prototype.getParentOrg = function(currentOrg) {
  if (!currentOrg) return false;
  var ml = this.getMainOrgList(), self = this;
  if (ml && ml[currentOrg]) {
    if (ml[currentOrg].isTopLevel) {
      return currentOrg;
    } else {
      if (ml[currentOrg].parentOrgId) return self.getParentOrg(ml[currentOrg].parentOrgId);
      else return currentOrg;
    };
  } else return false;
};
AdminTool.prototype.getUserParentOrgs = function() {
  var uo = this.getUserOrgs(), parentList = [], self = this;
  if (uo) {
    uo.forEach(function(o) {
      var p = self.getParentOrg(o);
      if (p && !self.inArray(p, parentList))  {
        parentList.push(p);
      };
    });
    return parentList;
  } else return false;
};
AdminTool.prototype.getTopLevelOrgs = function() {
  var ml = this.getMainOrgList(), orgList = [];
  for (var org in ml) {
    if (ml[org].isTopLevel) orgList.push(org);
  };
  return orgList;
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
        OT.populateOrgsList(data.entry);
        OT.populateUI();
        if (!noPatientData) {
          self.getHereBelowOrgs();
          OT.filterOrgs(self.here_below_orgs);
        };
        $("#dataDownloadModal").on('shown.bs.modal', function () {
              var parentOrgList = AT.getUserParentOrgs();
              if (parentOrgList && parentOrgList.length > 0) {
                 var instrumentList = AT.getInstrumentList();
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
            if ((self.here_below_orgs).length == 1 || (iterated && request_org_list && request_org_list[$(this).val()])) $(this).prop("checked", true);
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
    '20000': ['eortc', 'hpfs', 'prems', 'irondemog']
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


