//a workaround for wrapper not finished loading before the content displays, the finish loading of wrapper hides the loader
DELAY_LOADING = true;

var AdminTool = function() {
  var requestsCounter = 0;

  this.userOrgs = [];

  this.fadeLoader = function() {
      DELAY_LOADING = false;
      setTimeout('$("#loadingIndicator").fadeOut();', 300);
  };
  this.getData = function(userString) {
    var self = this;
    $.ajax ({
        type: "GET",
        url: '/api/consent-assessment-status',
        contentType: "application/json; charset=utf-8",
        data: userString,
        timeout: 10000,
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
                  if (!prevItem.consent_signed || ((prevItem.assessment_status != item.assessment_status)
                      && (prevItem.consent_signed != item.consent.signed))){
                    if (!(/null/.test(item.consent.agreement_url))) {
                      var cl = "";
                      var sd = item.consent.signed? (item.consent.signed).substring(0, 10) : "";
                      switch(String(item.assessment_status).toLowerCase()) {
                          case "completed":
                            cl = "text-success";
                            break;
                          case "due":
                            cl = "text-warning";
                            break;
                          case "overdue":
                            cl = "text-danger";
                            break;
                      };
                      a += (a != "" ? "<br/>" : "") + "<span class='" + cl + " small-text'>" + item.assessment_status + "</span>";
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
               //var row = $("#adminTable tr[data-uniqueid='" + d.id + "']");
               var row = $("#id_row_" + d.id);
               if (row.length > 0) {
                  var rindex = row.attr("data-index");
                  var statusField = row.children(".status-field");
                  var cdField = row.children(".consentdate-field");
                 //console.log("status: " + statusField.length + " cdField: " + cdField.length);
                 if (d.data.status) statusField.html(d.data.status);
                 if (d.data.consentdate) cdField.html(d.data.consentdate);
                };
            });

          };
        };
        //console.log("consent updated successfully.");
        requestsCounter -= 1;
        if(requestsCounter == 0) self.fadeLoader();
    }).fail(function(xhr) {
        //console.log("request failed.");
        self.fadeLoader();
    });
  };

  this.updateData = function() {

    var us = "", _userIds = [], ct = 0, arrUsers = [];
    var self = this;

    $("td.id-field").each(function() {
        var id = parseInt($(this).text());
        if (!isNaN(id)) {
            _userIds.push(id);
        };
     });

    for (var index = 0; index < _userIds.length; index++, ct++) {

       us += (us != ""?"&":"") + "user_id=" + _userIds[index];
       if (index == (_userIds.length - 1)) {
         arrUsers.push(us);
       }
       else if (ct >= 10) {
          arrUsers.push(us);
          us = "";
          ct = 0;
       };
    };

    if (arrUsers.length > 0) {
      requestsCounter = arrUsers.length;
      loader(true);
      arrUsers.forEach(function(us) {
          try {
            AT.getData(us);
          } catch(ex) {
            //console.log("Error request: " + ex.message);
            self.fadeLoader();
          };
      });
    } else {
      self.fadeLoader();
    };
  };
  this.setUserOrg = function(userId) {
    var self = this;
    $.ajax ({
            type: "GET",
            url: '/api/demographics/'+userId
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
  this.getUserOrgs = function() {
    return this.userOrgs;
  };
  this.initOrgsList = function(userId, leafOrgs, request_org_list) {
      AT.setUserOrg(userId);
      var noPatientData = $("#admin-table-body").find("tr.no-records-found").length > 0;
      if (!noPatientData) {
        $.ajax ({
            type: "GET",
            url: '/api/organization'
        }).done(function(data) {

            OT.populateOrgsList(data.entry);
            OT.populateUI();
            var orgsList = OT.getOrgsList();
            if (leafOrgs) {
               //console.log(leafOrgs)
               OT.filterOrgs(leafOrgs);
            };
            //console.log(orgsList)
            $("#userOrgs input[name='organization']").each(function() {
                if (request_org_list && request_org_list[$(this).val()]) $(this).prop("checked", true);
                $(this).on("click", function() {
                    var orgsList = [];
                    $("#userOrgs input[name='organization']").each(function() {
                        if ($(this).is(":checked")) orgsList.push($(this).val());
                    });
                    if (orgsList.length > 0) {
                      location.replace("/patients/?org_list=" + orgsList.join(","));
                    } else location.replace("/patients");
                });
            });
        }).fail(function() {
            //console.log("Problem retrieving data from server.");
        });

      //orglist-dropdown
      $('#orglist-dropdown').on('click', function () {
          setTimeout('AT.setOrgsMenuHeight();', 0);
      });
    } else {
      //no patient data
      $("#patientAssessmentDownload").hide();
      $("#orglistSelector").hide();
   };
  };

  this.setOrgsMenuHeight = function() {
    var h = parseInt($("#fillOrgs").height());
    if (!isNaN(h) && h > 0) $("#org-menu").height(h + 50);
  };

};

var AT = new AdminTool();