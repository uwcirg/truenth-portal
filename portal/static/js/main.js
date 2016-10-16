/*** Portal specific javascript. Topnav.js is separate and will be used across domains. **/

var userSetLang = 'en_US';// FIXME scope? defined in both tnth.js/banner and main.js

function equalHeightBoxes(passClass) {
    var windowsize = $(window).width();
    // Switch back to auto for small screen or to recalculate on larger
    $('.'+passClass).css("height","auto");
    if (windowsize > 768 && $('.'+passClass).length > 1) {
        var elementHeights = $('.'+passClass).map(function() {
            return $(this).height();
        }).get();
        // Math.max takes a variable number of arguments
        // `apply` is equivalent to passing each height as an argument
        var maxHeight = Math.max.apply(null, elementHeights);
        // Set each height to the max height
        $('.'+passClass).height(maxHeight);
    }
}

// Return an XHR without XHR header so  it doesn't need to be explicitly allowed with CORS
function xhr_function(){
    // Get new xhr object using default factory
    var xhr = jQuery.ajaxSettings.xhr();
    // Copy the browser's native setRequestHeader method
    var setRequestHeader = xhr.setRequestHeader;
    // Replace with a wrapper
    xhr.setRequestHeader = function(name, value) {
        // Ignore the X-Requested-With header
        if (name == 'X-Requested-With') return;
        // Otherwise call the native setRequestHeader method
        // Note: setRequestHeader requires its 'this' to be the xhr object,
        // which is what 'this' is here when executed.
        setRequestHeader.call(this, name, value);
    };
    // pass it on to jQuery
    return xhr;
}
// AJAX callback
function embed_page(data){
    $("#mainNav")
        // Embed data returned by AJAX call into container element
        .html(data).promise().done(function() {
            //for firefox? need to figure out why it doesn't show the content if not deling this call??
            if(navigator.userAgent.toLowerCase().indexOf('firefox') > -1){
                setTimeout("showWrapper();loader();", 100);
                //console.log("in firefox")
            } else setTimeout("showWrapper();loader();", 0);

        });
    // Wait until TrueNTH logo loads before displaying the navWrapper. Avoid having content flash when CSS hasn't loaded
    // $("img.tnth-topnav-wordmark").load(function(){

    // });
    // Todo: add "data-*" HTML attribute
}

function showMain() {

    $("#mainHolder").css({
                          "visibility" : "visible",
                          "-ms-filter": "progid:DXImageTransform.Microsoft.Alpha(Opacity=100)",
                          "filter": "alpha(opacity=100)",
                          "-moz-opacity": 1,
                          "-khtml-opacity": 1,
                          "opacity": 1
                        });

}

function showWrapper() {
    //$("#tnthNavWrapper").show();
    //adding this for firefox fix
    $("#tnthNavWrapper").css({"visibility":"visible", "display": "block"});
}

// Loading indicator that appears in UI on page loads and when saving
var loader = function(show) {
    //landing page
    if ($("#fullSizeContainer").length > 0) {
        $("#loadingIndicator").hide();
        showMain();
        return false;
    };

    if (show) {
        // $("#profileForm").addClass("loading");
        $("#loadingIndicator").show();
    } else {
        // Otherwise we'll hide it
        showMain();
        // $("#profileForm").removeClass("loading");
        $("#loadingIndicator").fadeOut();
    };
};

var fillContent = {
    "clinical": function(data) {
        $.each(data.entry, function(i,val){
            var clinicalItem = val.content.code.coding[0].display;
            if (clinicalItem == "PCa diagnosis") {
                clinicalItem = "pca_diag";
            } else if (clinicalItem == "treatment begun") {
                clinicalItem = "tx";
            } else if (clinicalItem == "PCa localized diagnosis") {
                clinicalItem = "pca_localized";
            }
            $('div[data-topic='+clinicalItem+']').fadeIn().next().fadeIn();
            var clinicalValue = val.content.valueQuantity.value;
            var $radios = $('input:radio[name='+clinicalItem+']');
            if($radios.is(':checked') === false) {
                $radios.filter('[value='+clinicalValue+']').prop('checked', true);
            }
            // Display clinics if any value is false (except localized) or if all are answered
            if ((clinicalValue == "false" && clinicalItem != "pca_localized") || i == 3) {
                $("#clinics").fadeIn();
            }
        })
    },
    "demo": function(data) {
        $('#firstname').val(data.name.given);
        $('#lastname').val(data.name.family);
        if (data.birthDate) {
            var bdArray = data.birthDate.split("-");
            $("#birthday").val(data.birthDate);
            $("#year").val(bdArray[0]);
            $("#month").val(bdArray[1]);
            $("#date").val(bdArray[2]);
            // If there's already a birthday, then we should show the patientQ if this is a patient (determined with roles)
            $("#patBiopsy").fadeIn();
        }
        // TODO - add email and phone for profile page use
        // Only on profile page
        $.each(data.extension[0].valueCodeableConcept.coding,function(i,val){
            $("#userEthnicity input:radio[value="+val.code+"]").prop('checked', true);
            // Way to handle non-standard codes - output but hide, for submitting on update
            if ($("#userEthnicity input:radio[value="+val.code+"]").length == 0) {
                $("#userEthnicity").append("<input class='tnth-hide' type='checkbox' checked name='ethnicity' value='"+val.code+"' data-label='"+val.display+"' />");
            }
        });
        // Get Races
        $.each(data.extension[1].valueCodeableConcept.coding,function(i,val){
            $("#userRace input:checkbox[value="+val.code+"]").prop('checked', true);
            // Way to handle non-standard codes
            if ($("#userRace input:checkbox[value="+val.code+"]").length == 0) {
                // If there is any non-standard, then check the "other" in the UI
                $("#userRace input:checkbox[value=2131-1]").prop('checked', true);
                // Add hidden list of non-standard for form submission
                $("#userRace").append("<input class='tnth-hide' type='checkbox' checked name='race' value='"+val.code+"' data-label='"+val.display+"' />");
                //$("#raceOtherVal").fadeToggle();
            }
        });
    },
    "name": function(data){
        if (data && data.name) {
            $('#firstname').val(data.name.given);
            $('#lastname').val(data.name.family);
        };
    },
    "dob": function(data) {
        if (data && data.birthDate) {
            var bdArray = data.birthDate.split("-");
            $("#birthday").val(data.birthDate);
            $("#year").val(bdArray[0]);
            $("#month").val(bdArray[1]);
            $("#date").val(bdArray[2]);
            // If there's already a birthday, then we should show the patientQ if this is a patient (determined with roles)
            if ($("#patBiopsy").length > 0) $("#patBiopsy").fadeIn();
        };
    },
    "orgs": function(data) {
        $.each(data.careProvider,function(i,val){
            var orgID = val.reference.split("/").pop();
            $("body").find("#userOrgs input.clinic:checkbox[value="+orgID+"]").prop('checked', true);
        });
        // If there's a pre-selected clinic set in session, then fill it in here (for initial_queries)
        if ( typeof preselectClinic !== 'undefined' && preselectClinic !== "None" ) {
            $("body").find("#userOrgs input.clinic:checkbox[value="+preselectClinic+"]").prop('checked', true);
        }
        if ($('#userOrgs input.clinic:checked').size()) {
            $("#terms").fadeIn();
        }
    },
    "proceduresContent": function(data,newEntry) {
        if (data.entry.length == 0) {
            $("body").find("#userProcedures").html("<p id='noEvents' style='margin: 0.5em 0 0 1em'><em>You haven't entered any treatments yet.</em></p>").animate({opacity: 1});
            return false;
        }

        // sort from newest to oldest
        data.entry.sort(function(a,b){
            return new Date(b.resource.performedDateTime) - new Date(a.resource.performedDateTime);
        });
        var proceduresHtml = '<ul id="eventListtnthproc">';

        // If we're adding a procedure in-page, then identify the highestId (most recent) so we can put "added" icon
        var highestId = 0;
        $.each(data.entry,function(i,val){
            var procID = val.resource.id;
            var displayText = val.resource.code.coding[0].display;
            var performedDateTime = val.resource.performedDateTime;
            var performedDate = new Date(performedDateTime);
            proceduresHtml += "<li data-id='" + procID + "' style='margin: 8px 0'>" + performedDate.toLocaleDateString()  + " -- " + displayText + "  <a data-toggle='popover' class='btn btn-default btn-xs confirm-delete' data-content='Are you sure you want to delete this treatment?<br /><br /><a href=\"#\" class=\"btn-delete btn btn-tnth-primary\">Yes</a> &nbsp;&nbsp;&nbsp; <a class=\"btn btn-default cancel-delete\">No</a>' rel='popover'><i class='fa fa-times'></i> Delete</a></li>";
            if (procID > highestId) {
                highestId = procID;
            }
        });
        proceduresHtml += '</ul>';
        $("body").find("#userProcedures").html(proceduresHtml).animate({opacity: 1});
        // If newEntry, then add icon to what we just added
        if (newEntry) {
            $("body").find("li[data-id='" + highestId + "']").append("&nbsp; <small class='text-success'><i class='fa fa-check-square-o'></i> <em>Added!</em></small>");
        }
        $('[data-toggle="popover"]').popover({
            trigger: 'click',
            placement: 'right',
            html: true
        });
    },
    "roleList": function(data) {
        data.roles.forEach(function(role) {
            $("#rolesGroup").append("<div class='checkbox'><label><input type='checkbox' name='user_type' value='" + role.name + "' >" + role.name.replace("_", " ").replace(/\b[a-z]/g,function(f){return f.toUpperCase();}) + "</label></div>");
        });
    },
    "roles": function(data,isProfile) {
        $.each(data.roles, function(i,val){
            var userRole = val.name;
            // Handle profile differently than initial_queries
            if (isProfile) {
                $.each(data.roles,function(i,val){
                    $("#rolesGroup input:checkbox[value="+val.name+"]").prop('checked', true);
                });
            } else {
                var $radios = $('input[name=user_type]');
                if($radios.is(':checked') === false) {
                    $radios.filter('[value='+userRole+']').prop('checked', true);
                }
                if (userRole == "patient") {
                    $("#bdGroup").fadeIn();
                    $("#patientQ").fadeIn();
                    $("#clinics").hide();
                    return false;
                } else if (userRole == "partner") {
                    $("#clinics").fadeIn();
                    $("#patientQ, #bdGroup").hide();
                }
            }
        });
    }
};

var assembleContent = {
    "demo": function(userId,onProfile) {
        var demoArray = {};
        demoArray["resourceType"] = "Patient";
        demoArray["name"] = {
            "given": $("input[name=firstname]").val(),
            "family": $("input[name=lastname]").val()
        };
        demoArray["birthDate"] = $("input[name=birthDate]").val();
        if (onProfile) {
            $.each($("#userOrgs input:checkbox:checked"),function(i,v){
                if ($(this).attr("data-parent-id")) {
                    $("#userOrgs input:checkbox[value="+$(this).attr("data-parent-id")+"]").prop('checked', true);
                }
            });
            var orgIDs = $("#userOrgs input:checkbox:checked").map(function(){
                return { reference: "api/organization/"+$(this).val() };
            }).get();
            var parentId;
            $.each($("#userOrgs input:checkbox:checked"),function(i,v){
                if ($(this).attr("data-parent-id") && $(this).attr("data-parent-id") != parentId) {
                    orgIDs.push({reference: "api/organization/"+$(this).attr("data-parent-id")});
                    parentId = $(this).attr("data-parent-id");
                }
            });
            demoArray["careProvider"] = orgIDs;

            // Grab profile field values - looks for regular and hidden, can be checkbox or radio
            var ethnicityIDs = $("#userEthnicity input:checked").map(function(){
                return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Ethnicity" };
            }).get();
            // Look for race checkboxes, can be hidden
            var raceIDs = $("#userRace input:checkbox:checked").map(function(){
                return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Race" };
            }).get();
            demoArray["gender"] = $("input[name=sex]:checked").val();
            demoArray["telecom"] = [
                { "system": "email", "value": $("input[name=email]").val() },
                { "system": "phone", "value": $("input[name=phone]").val() }
            ];


            demoArray["extension"] = [
                { "url": "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity",
                    "valueCodeableConcept": {
                        "coding": ethnicityIDs
                    }
                },
                { "url": "http://hl7.org/fhir/StructureDefinition/us-core-race",
                    "valueCodeableConcept": {
                        "coding": raceIDs
                    }
                }
            ];

           //console.log("demoArray", demoArray);
        }
        tnthAjax.putDemo(userId,demoArray);
        //if (demoArray["roles"]) {
            //tnthAjax.putRoles(userId,demoArray["roles"]);
        //};
    },
    "name": function(userId) {

        var firstName = $("input[name=firstname]").val();
        var lastName = $("input[name=lastname]").val();
        if (firstName != "" && lastName != "") {
            var demoArray = {};
            demoArray["resourceType"] = "Patient";
            demoArray["name"] = {
                "given": $("input[name=firstname]").val(),
                "family": $("input[name=lastname]").val()
            };
            tnthAjax.putDemo(userId,demoArray);
        };

    },
    "dob": function(userId) {
        var demoArray = {};
        var birthday = $("input[name='birthDate']").val();
        var month = $("#month").find("option:selected").val();
        var day = $("input[name='birthdayDate']").val();
        var year = $("input[name='birthdayYear']").val();
        var birthDate = "";

        if (birthday == "") {
            if (month != "" && day != "" && year != "") {
                birthDate = year + "-" + month + "-" + day;
            };
        };
        if (birthday  != "" || birthDate != "") {
            demoArray["resourceType"] = "Patient";
            demoArray["birthDate"] = (birthday != "" ? birthday: birthDate);
            tnthAjax.putDemo(userId,demoArray);
        }
    },
    "orgs": function(userId) {
        $.each($("#userOrgs input:checkbox:checked"),function(i,v){
            if ($(this).attr("data-parent-id")) {
                $("#userOrgs input:checkbox[value="+$(this).attr("data-parent-id")+"]").prop('checked', true);
            }
        });

        var orgIDs = $("#userOrgs input:checkbox:checked").map(function(){
            return { reference: "api/organization/"+$(this).val() };
        }).get();
        if (typeof orgIDs === 'undefined'){
            orgIDs = [0]  // special value for `none of the above`
        }
        var demoArray = {};
        demoArray["resourceType"] = "Patient";
        demoArray["careProvider"] = orgIDs;
        tnthAjax.putDemo(userId, demoArray);
    },
    "coreData": function(userId) {
        var demoArray = {};
        demoArray["resourceType"] = "Patient";
        demoArray["extension"] = [];
        if ($("#userEthnicity").length) {
            var ethnicityIDs = $("#userEthnicity input:checked").map(function(){
                return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Ethnicity" };
            }).get();
            demoArray["extension"].push(
                { "url": "http://hl7.org/fhir/StructureDefinition/us-core-ethnicity",
                    "valueCodeableConcept": {
                        "coding": ethnicityIDs
                    }
                }
            );
        }
        if ($("#userRace").length) {
            var raceIDs = $("#userRace input:checkbox:checked").map(function(){
                return { code: $(this).val(), system: "http://hl7.org/fhir/v3/Race" };
            }).get();
            demoArray["extension"].push(
                { "url": "http://hl7.org/fhir/StructureDefinition/us-core-race",
                    "valueCodeableConcept": {
                        "coding": raceIDs
                    }
                }
            );
        }
        tnthAjax.putDemo(userId,demoArray);
    }
};

var tnthAjax = {
    "getOrgs": function(userId, noOverride) {
        loader(true);
        $.ajax ({
            type: "GET",
            url: '/api/organization'
        }).done(function(data) {
            var clinicArray = [];
            $.each(data.entry,function(i,val){
                if (val.partOf) {
                    // Child clinic
                    var getParent = val.partOf.reference.split("/").pop();
                    jQuery.map(clinicArray, function(obj) {
                        if(obj.id === parseInt(getParent))
                            obj.children.push({
                                "id": val.id,
                                "name": val.name
                            });
                    });
                } else {
                    // Parent clinic
                    clinicArray.push({
                        id: val.id,
                        name: val.name,
                        children: []
                    });
                }
            });
            $.each(clinicArray, function(i,val) {
                // Fill in parent clinic
                if (val.name != "none of the above" && (val.children.length > 0)) {
                    $("#fillOrgs").append("<legend style='margin: 0  0 4px'>"+val.name+"</legend><input class='tnth-hide' type='checkbox' name='organization' id='" + val.id + "_org' value='"+val.id+"' />");
                }
                // Fill in each child clinic
                if (val.children.length > 0) {
                    $.each(val.children, function(n,subval) {
                        var childClinic = '<div class="checkbox"><label>' +
                            '<input class="clinic init-queries-field" type="checkbox" name="organization" id="' +  subval.id + '_org" value="'+
                            subval.id +'" data-parent-id="'+val.id+'" />'+
                            subval.name +
                            '</label></div>';
                       $("#fillOrgs").append(childClinic);
                    });
                }
            });
            tnthAjax.getDemo(userId, noOverride);
            //tnthAjax.getProc(userId);//TODO add html for that, see #userProcedures
        }).fail(function() {
            console.log("Problem retrieving data from server.");
            loader();
        });
    },
    "getDemo": function(userId, noOverride) {
        $.ajax ({
            type: "GET",
            url: '/api/demographics/'+userId
        }).done(function(data) {
            fillContent.orgs(data);
            if (!noOverride) fillContent.demo(data);
            loader();
        }).fail(function() {
            console.log("Problem retrieving data from server.");
            loader();
        });
    },
    "putDemo": function(userId,toSend) {
        $.ajax ({
            type: "PUT",
            url: '/api/demographics/'+userId,
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify(toSend)
        }).done(function(data) {
        }).fail(function() {
            console.log("Problem updating demographics on server." + JSON.stringify(toSend));
        });
    },
    "getDob": function(userId) {
        $.ajax ({
            type: "GET",
            url: '/api/demographics/'+userId
        }).done(function(data) {
            fillContent.dob(data);
            loader();
        }).fail(function() {
            console.log("Problem retrieving data from server.");
            loader();
        });
    },
    "getName": function(userId) {
        $.ajax ({
            type: "GET",
            url: '/api/demographics/'+userId
        }).done(function(data) {
            fillContent.name(data);
            loader();
        }).fail(function() {
            console.log("Problem retrieving data from server.");
            loader();
        });
    },
    "getProc": function(userId,newEntry) {
        $.ajax ({
            type: "GET",
            url: '/api/patient/'+userId+'/procedure'
        }).done(function(data) {
            fillContent.proceduresContent(data,newEntry);
        }).fail(function() {
            console.log("Problem retrieving data from server.");
        });
    },
    "postProc": function(userId,toSend) {
        $.ajax ({
            type: "POST",
            url: '/api/procedure',
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify(toSend)
        }).done(function(data) {
        }).fail(function() {
            console.log("Problem updating procedure on server.");
        });
    },
    "deleteProc": function(procedureId) {
        $.ajax ({
            type: "DELETE",
            url: '/api/procedure/'+procedureId,
            contentType: "application/json; charset=utf-8",
        }).done(function(data) {
        }).fail(function() {
            console.log("Problem deleting procedure on server.");
        });
    },
    "getRoleList": function() {
        $.ajax({
            type: "GET",
            url: "/api/roles",
            async: false
        }).done(function(data) {
            fillContent.roleList(data);
        });
    },
    "getRoles": function(userId,isProfile) {
        var self = this;
        $.ajax ({
            type: "GET",
            url: '/api/user/'+userId+'/roles'
        }).done(function(data) {
            //self.getRoleList();
            fillContent.roles(data,isProfile);
        }).fail(function() {
            console.log("Problem retrieving data from server.");

        });
    },
    "putRoles": function(userId,toSend) {
        $.ajax ({
            type: "PUT",
            url: '/api/user/'+userId+'/roles',
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify(toSend)
        }).done(function(data) {

        }).fail(function(jhr) {
            console.log("Problem updating role on server.");
           //console.log(jhr.responseText);

        });
    },
    "deleteRoles": function(userId,toSend) {
        $.ajax ({
            type: "DELETE",
            url: '/api/user/'+userId+'/roles',
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify(toSend)
        }).done(function(data) {

        }).fail(function() {
            console.log("Problem updating role on server.");

        });
    },
    "getClinical": function(userId) {
        $.ajax ({
            type: "GET",
            url: '/api/patient/'+userId+'/clinical'
        }).done(function(data) {
            fillContent.clinical(data);
        }).fail(function() {
            console.log("Problem retrieving data from server.");
        });
    },
    "putClinical": function(userId, toCall, toSend) {
        $.ajax ({
            type: "POST",
            url: '/api/patient/'+userId+'/clinical/'+toCall,
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify({value: toSend})
        }).done(function() {

        }).fail(function() {
            alert("There was a problem saving your answers. Please try again.");
        });
    },
    "postTerms": function(toSend) {
        $.ajax ({
            type: "POST",
            url: '/api/tou/accepted',
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            data: JSON.stringify(toSend)
        }).done(function() {
            console.log('terms stored');
        }).fail(function() {
            alert("There was a problem saving your answers. Please try again.");
        });
    }
};

$(document).ready(function() {

    if (typeof PORTAL_NAV_PAGE != 'undefined') {

        loader(true);

        var initial_xhr = $.ajax({
            url: PORTAL_NAV_PAGE,
            type:'GET',
            contentType:'text/plain',
            cache: true,
            //dataFilter:data_filter,
            //xhr: xhr_function,
            crossDomain: true
            //xhrFields: {withCredentials: true},
        }, 'html')
        .done(function(data) {
            embed_page(data);
            //showSearch();
        })
        .fail(function(jqXHR, textStatus, errorThrown) {
            console.log("Error loading nav elements from " + PORTAL_HOSTNAME);
            loader();
        })
        .always(function() {
            // alert( "complete" );

        });
    } else loader();

    // Reveal footer after load to avoid any flashes will above content loads
    $("#homeFooter").show();

    // Handling "none of the above" clinic choice
    $("#userOrgs").on("click", ".clinic", function(){
        if ($(this).prop('checked')){
            if ($(this).attr("id") !== "noOrgs") {
                $("#noOrgs").attr('checked',false);
            } else {
                $("input[name='organization']:not(#noOrgs)").attr('checked',false);
            }
        }
    });

    // To validate a form, add class to <form> and validate by ID.
    $('form.to-validate').validator({
        custom: {
            birthday: function() {
                var m = parseInt($("#month").val());
                var d = parseInt($("#date").val());
                var y = parseInt($("#year").val());
                // If all three have been entered, run check
                var goodDate = false;
                var errorMsg = "Sorry, this isn't a valid date. Please try again.";
                if (m && d && y) {
                    var today = new Date();
                    // Check to see if this is a real date
                    var date = new Date(y,m-1,d);
                    if (date.getFullYear() == y && date.getMonth() + 1 == m && date.getDate() == d) {
                        goodDate = true;
                        // Only allow if birthdate is before today
                        if (date.setHours(0,0,0,0) >= today.setHours(0,0,0,0)) {
                            goodDate = false;
                            errorMsg = "Your birthdate must be in the past.";
                        }
                    }
                    if (y.toString().length < 3) {
                        goodDate = false;
                        errorMsg = "Please make sure you use a full 4-digit number for your birth year.";
                    }
                    if (y < 1900) {
                        goodDate = false;
                        errorMsg = "Year of birth must be after 1900.";
                    }
                    // After tests display errors if necessary
                    if (goodDate) {
                        $("#errorbirthday").hide();
                        // Set date if YYYY-MM-DD
                        $("#birthday").val(y+"-"+m+"-"+d);
                        // If we are on initial-queries, then we'll want to display the patientQ div
                        $("#patientQ, #patBiopsy").fadeIn();
                    } else {
                        $("#errorbirthday").html(errorMsg).show();
                        $("#birthday").val("");
                    }
                } else {
                    // If NaN then the values haven't been entered yet, so we
                    // validate as true until other fields are entered
                    if (isNaN(y) || (isNaN(d) && isNaN(y))) {
                        return true;
                    } else if (isNaN(d)) {
                        errorMsg = "Please enter a date.";
                    }
                    $("#errorbirthday").html(errorMsg).show();
                    $("#birthday").val("");
                }
                if (goodDate) {
                    return true;
                } else {
                    return false;
                }
            },
            customemail: function($el) {
                if ($el.val() == "") {
                    return false;
                }
                var emailReg = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
                // Add user_id to api call (used on patient_profile page so that staff can edit)
                var addUserId = "";
                if (typeof(patientId) !== "undefined") {
                    addUserId = "&user_id="+patientId;
                }
                // If this is a valid address, then use unique_email to check whether it's already in use
                if (emailReg.test($el.val())) {
                    $.ajax ({
                        type: "GET",
                        //url: '/api/unique_email?email='+encodeURIComponent($el.val())+addUserId
                        url: '/api/unique_email?email='+encodeURIComponent($el.val())+addUserId
                    }).done(function(data) {
                        if (data.unique) {
                            $("#erroremail").html('').parents(".form-group").removeClass('has-error');
                        } else {
                            $("#erroremail").html("This e-mail address is already in use. Please enter a different address.").parents(".form-group").addClass('has-error');
                        }
                    }).fail(function() {
                        console.log("Problem retrieving data from server.")
                    });
                }
                return emailReg.test( $el.val() );
            }
        },
        errors: {
            birthday: "Sorry, this isn't a valid date. Please try again.",
            customemail: "This isn't a valid e-mail address, please double-check."
        },
        disable: false
    }).off('input.bs.validator change.bs.validator'); // Only check on blur (turn off input and change)

});


var tnthDates = {
    /***
     * changeFormat - changes date format, particularly for submitting to server
     * @param currentDate - date to change
     * @param reverse - use to switch from yyyy-mm-dd to mm/dd/yyyy
     * @param shorten - removes padding from zeroes (only in reverse)
     * @returns - a date as a string
     *
     * If language is es_MX or en_AU then uses dd/mm/yyyy format
     *
     * Examples:
     * changeFormat("04/29/2016") returns "2016-04-29T07:00:00", converts according to getTimezoneOffset
     * changeFormat("2016-04-29",true) returns "04/29/2016"
     * changeFormat("2016-04-29",true,true) returns "4/29/2016"
     ***/
    "changeFormat": function(currentDate,reverse,shorten) {
        if (currentDate == null || currentDate == "") {
            return null;
        }
        var yearToPass, convertDate, dateFormatArray;
        if (reverse) {
            dateFormatArray = currentDate.split("-");
            yearToPass = dateFormatArray[0];
            if (shorten) {
                dateFormatArray[1] = dateFormatArray[1].replace(/^0+/, '');
                dateFormatArray[2] = dateFormatArray[2].replace(/^0+/, '');
            }
            if (userSetLang !== undefined && (userSetLang == 'es_MX' || userSetLang == 'en_AU')) {
                convertDate = dateFormatArray[2]+"/"+dateFormatArray[1]+"/"+yearToPass;
            } else {
                convertDate = dateFormatArray[1]+"/"+dateFormatArray[2]+"/"+yearToPass;
            }
        } else {
            dateFormatArray = currentDate.split("/");
            // If patient manuals enters two digit year, then add 19 or 20 to year.
            // TODO - this is susceptible to Y2K for 2100s. Be better to force
            // user to type 4 digits.
            var currentTime = new Date();
            if (dateFormatArray[2].length == 2) {
                var shortYear = currentTime.getFullYear().toString().substr(2,2);
                if (dateFormatArray[2] > shortYear) {
                    yearToPass = '19'+dateFormatArray[2];
                } else {
                    yearToPass = '20'+dateFormatArray[2];
                }
            } else {
                yearToPass = dateFormatArray[2];
            }
            if (userSetLang !== undefined && (userSetLang == 'es_MX' || userSetLang == 'en_AU')) {
                convertDate = yearToPass+"-"+dateFormatArray[1]+"-"+dateFormatArray[0]
            } else {
                convertDate = yearToPass+"-"+dateFormatArray[0]+"-"+dateFormatArray[1]
            }
            // add T according to timezone
            var tzOffset = currentTime.getTimezoneOffset();//minutes
            tzOffset /= 60;//hours
            if (tzOffset < 10) tzOffset = "0" + tzOffset;
            convertDate += "T" + tzOffset + ":00:00";
        }
        return convertDate
    },
    /***
     * parseDate - Fancier function for changing javascript date yyyy-mm-dd (with optional time) to a mm/dd/yyyy (optional time) format. Used with mPOWEr
     * @param date - the date to be converted
     * @param noReplace - prevent replacing any spaces with "T" to get in proper javascript format. 2016-02-24 15:28:09-0800 becomes 2016-02-24T15:28:09-0800
     * @param padZero - if true, will add padded zero to month and date
     * @param keepTime - if true, will output the time as part of the date
     * @param blankText - pass a value to display if date is null
     * @returns date as a string with optional time
     *
     * parseDate("2016-02-24T15:28:09-0800",true,false,true) returns "2/24/2016 3:28pm"
     */
    "parseDate": function(date,noReplace,padZero,keepTime,blankText) {
        if(date == null) {
            if (blankText) {
                return blankText;
            } else {
                return "";
            }
        }
        // Put date in proper javascript format
        if (noReplace == null) {
            date = date.replace(" ", "T");
        }
        // Need to reformat dates b/c of date format issues in Safari (and others?)
        // http://stackoverflow.com/questions/6427204/date-parsing-in-javascript-is-different-between-safari-and-chrome
        var a = date.split(/[^0-9]/);
        var toConvert;
        if (a[3]) {
            toConvert=new Date (a[0],a[1]-1,a[2],a[3],a[4],a[5]);
        } else {
            toConvert=new Date (a[0],a[1]-1,a[2]);
        }

        // Switch date to mm/dd/yyyy
        //var toConvert = new Date(Date.parse(date));
        var month = toConvert.getMonth() + 1;
        var day = toConvert.getDate();
        if (padZero) {
            if (month <= 9)
                month = '0' + month;
            if (day <= 9)
                day = '0' + day;
        }
        if (keepTime) {
            var amPm = "am";
            var hour = a[3];
            if (a[3] > 11) {
                amPm = "pm";
                if (a[3] > 12) {
                    hour = (a[3]-12);
                }
            }
            return month + "/" + day + "/" + toConvert.getFullYear()+" "+hour+":"+a[4]+amPm;
        } else {
            return month + "/" + day + "/" + toConvert.getFullYear();
        }
    },
    /***
     * parseForSorting - changes date to a YYYYMMDDHHMMSS string for sorting (note that this is a string rather than a number)
     * @param date - the date to be converted
     * @param noReplace - prevent replacing any spaces with "T" to get in proper javascript format. 2016-02-24 15:28:09-0800 becomes 2016-02-24T15:28:09-0800. Adding T indicates UTC time
     * @returns date as a string used by system for sorting
     *
     * parseDate("2016-02-24T15:28:09-0800",true) returns "201600224152809"
     */
    "parseForSorting": function(date,noReplace) {
        if (date == null) {
            return ""
        }
        // Put date in proper javascript format
        if (noReplace == null) {
            date = date.replace(" ", "T");
        }
        // Need to reformat dates b/c of date format issues in Safari (and others?)
        // http://stackoverflow.com/questions/6427204/date-parsing-in-javascript-is-different-between-safari-and-chrome
        var a = date.split(/[^0-9]/);
        var toConvert=new Date (a[0],a[1]-1,a[2],a[3],a[4],a[5]);
        // Switch date to mm/dd/yyyy
        //var toConvert = new Date(Date.parse(date));
        var month = toConvert.getMonth() + 1;
        var day = toConvert.getDate();
        if (month <= 9)
            month = '0' + month;
        if (day <= 9)
            day = '0' + day;
        return toConvert.getFullYear() + month + day + a[3] + a[4] + a[5]

    },
    /***
     * spellDate - spells out date in a format based on language/local. Currently not in use.
     * @param passDate - date to use. If empty, defaults to today.
     * @param ymdFormat - false by default. false = mm/dd/yyyy. true = yyyy-mm-dd
     * @returns spelled out date, localized
     */
    "spellDate": function(passDate,ymdFormat) {
        var todayDate = new Date();
        if (passDate) {
            // ymdFormat is true, we are assuming it's being received as YYYY-MM-DD
            if (ymdFormat) {
                todayDate = passDate.split("-");
                todayDate = new Date(todayDate[2], todayDate[0] - 1, todayDate[1])
            } else {
                // Otherwide mm/dd/yyyy
                todayDate = passDate.split("/");
                todayDate = new Date(todayDate[2], todayDate[0] - 1, todayDate[1])
            }
        }
        var returnDate;
        var monthNames = ["January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        // If user's language is Spanish then use dd/mm/yyyy format and changes words
        if (userSetLang !== undefined && userSetLang == 'es_MX') {
            monthNames = ["enero","febrero","marzo","abril","mayo","junio","julio", "agosto","septiembre","octubre","noviembre","diciembre"];
            returnDate = ('0' + todayDate.getDate()).slice(-2)+" de "+monthNames[todayDate.getMonth()]+" de "+todayDate.getFullYear()
        } else if(userSetLang !== undefined && userSetLang == "en_AU") {
            returnDate = ('0' + todayDate.getDate()).slice(-2)+" "+monthNames[todayDate.getMonth()]+" "+todayDate.getFullYear()
        } else {
            returnDate = monthNames[todayDate.getMonth()]+" "+('0' + todayDate.getDate()).slice(-2)+", "+todayDate.getFullYear()
        }
        return returnDate
    },
    /***
     * Calculates number of days between two dates. Used in mPOWEr for surgery/discharge
     * @param startDate - required. Assumes YYYY-MM-DD. This is typically the date of surgery or discharge
     * @param dateToCalc - optional. If empty, then assumes today's date
     * @returns number of days
     */
    "getDateDiff": function(startDate,dateToCalc) {
        var a = startDate.split(/[^0-9]/);
        var dateTime = new Date(a[0], a[1]-1, a[2]).getTime();
        var d;
        if (dateToCalc) {
            var c = dateToCalc.split(/[^0-9]/);
            d = new Date(c[0], c[1]-1, c[2]).getTime()
        } else {
            // If no baseDate, then use today to find the number of days between dateToCalc and today
            d = new Date().getTime()
        }
        // Round down to floor so we don't add an extra day if session is 12+ hours into the day
        return Math.floor((d - dateTime) / (1000 * 60 * 60 * 24))
    },
    "getAge": function (birthDate, otherDate) {
        birthDate = new Date(birthDate);
        // Use today's date to calc, unless otherwise specified
        var secondDate = new Date();
        if (otherDate) {
            secondDate = new Date(otherDate);
        }
        var years = (secondDate.getFullYear() - birthDate.getFullYear());

        if (secondDate.getMonth() < birthDate.getMonth() ||
            secondDate.getMonth() == birthDate.getMonth() && secondDate.getDate() < birthDate.getDate()) {
            years--;
        }
        return years;
    },
    /***
     * Simple function to add "days" label to a number of days. Not localized, used for mPOWEr
     * @param dateVal - required. Often derived via getDateDiff
     * @returns {string}
     */
    "addDays": function(dateVal) {
        var toReturn = "N/A";
        if (dateVal && typeof dateVal != undefined) {
            if (dateVal == 1) {
                toReturn = "1 day";
            } else if (dateVal < 0) {
                toReturn = "--";
            } else {
                toReturn = dateVal + " days";
            }
        } else if (dateVal === 0) {
            toReturn = "Today";
        }
        return toReturn
    }
};

/***
 * Bootstrap datatables functions
 * Uses http://bootstrap-table.wenzhixin.net.cn/documentation/
 ****/

var tnthTables = {
    /***
     * Quick way to sort when text is wrapper in an <a href> or other tag
     * @param a,b - the two items to compare
     * @returns 1,-1 or 0 for sorting
     */
    "stripLinksSorter": function(a,b) {
        a = $(a).text();
        b = $(b).text();
        var aa = parseFloat(a);
        var bb = parseFloat(b);
        //if (aa > bb) return 1;
        //if (aa < bb) return -1;
        //return 0;
        return  bb - aa;
    }
};


/**
 * Protect window.console method calls, e.g. console is not defined on IE
 * unless dev tools are open, and IE doesn't define console.debug
 */
(function() {
    var console = (window.console = window.console || {});
    var noop = function () {};
    var log = console.log || noop;
    var start = function(name) { return function(param) { log("Start " + name + ": " + param); } };
    var end = function(name) { return function(param) { log("End " + name + ": " + param); } };

    var methods = {
        // Internet Explorer (IE 10): http://msdn.microsoft.com/en-us/library/ie/hh772169(v=vs.85).aspx#methods
        // assert(test, message, optionalParams), clear(), count(countTitle), debug(message, optionalParams), dir(value, optionalParams), dirxml(value), error(message, optionalParams), group(groupTitle), groupCollapsed(groupTitle), groupEnd([groupTitle]), info(message, optionalParams), log(message, optionalParams), msIsIndependentlyComposed(oElementNode), profile(reportName), profileEnd(), time(timerName), timeEnd(timerName), trace(), warn(message, optionalParams)
        // "assert", "clear", "count", "debug", "dir", "dirxml", "error", "group", "groupCollapsed", "groupEnd", "info", "log", "msIsIndependentlyComposed", "profile", "profileEnd", "time", "timeEnd", "trace", "warn"

        // Safari (2012. 07. 23.): https://developer.apple.com/library/safari/#documentation/AppleApplications/Conceptual/Safari_Developer_Guide/DebuggingYourWebsite/DebuggingYourWebsite.html#//apple_ref/doc/uid/TP40007874-CH8-SW20
        // assert(expression, message-object), count([title]), debug([message-object]), dir(object), dirxml(node), error(message-object), group(message-object), groupEnd(), info(message-object), log(message-object), profile([title]), profileEnd([title]), time(name), markTimeline("string"), trace(), warn(message-object)
        // "assert", "count", "debug", "dir", "dirxml", "error", "group", "groupEnd", "info", "log", "profile", "profileEnd", "time", "markTimeline", "trace", "warn"

        // Firefox (2013. 05. 20.): https://developer.mozilla.org/en-US/docs/Web/API/console
        // debug(obj1 [, obj2, ..., objN]), debug(msg [, subst1, ..., substN]), dir(object), error(obj1 [, obj2, ..., objN]), error(msg [, subst1, ..., substN]), group(), groupCollapsed(), groupEnd(), info(obj1 [, obj2, ..., objN]), info(msg [, subst1, ..., substN]), log(obj1 [, obj2, ..., objN]), log(msg [, subst1, ..., substN]), time(timerName), timeEnd(timerName), trace(), warn(obj1 [, obj2, ..., objN]), warn(msg [, subst1, ..., substN])
        // "debug", "dir", "error", "group", "groupCollapsed", "groupEnd", "info", "log", "time", "timeEnd", "trace", "warn"

        // Chrome (2013. 01. 25.): https://developers.google.com/chrome-developer-tools/docs/console-api
        // assert(expression, object), clear(), count(label), debug(object [, object, ...]), dir(object), dirxml(object), error(object [, object, ...]), group(object[, object, ...]), groupCollapsed(object[, object, ...]), groupEnd(), info(object [, object, ...]), log(object [, object, ...]), profile([label]), profileEnd(), time(label), timeEnd(label), timeStamp([label]), trace(), warn(object [, object, ...])
        // "assert", "clear", "count", "debug", "dir", "dirxml", "error", "group", "groupCollapsed", "groupEnd", "info", "log", "profile", "profileEnd", "time", "timeEnd", "timeStamp", "trace", "warn"
        // Chrome (2012. 10. 04.): https://developers.google.com/web-toolkit/speedtracer/logging-api
        // markTimeline(String)
        // "markTimeline"

        assert: noop, clear: noop, trace: noop, count: noop, timeStamp: noop, msIsIndependentlyComposed: noop,
        debug: log, info: log, log: log, warn: log, error: log,
        dir: log, dirxml: log, markTimeline: log,
        group: start('group'), groupCollapsed: start('groupCollapsed'), groupEnd: end('group'),
        profile: start('profile'), profileEnd: end('profile'),
        time: start('time'), timeEnd: end('time')
    };

    for (var method in methods) {
        if ( methods.hasOwnProperty(method) && !(method in console) ) { // define undefined methods as best-effort methods
            console[method] = methods[method];
        }
    }
})();


//Promise polyfill - IE doesn't support Promise - so need this
!function(e){function n(){}function t(e,n){return function(){e.apply(n,arguments)}}function o(e){if("object"!=typeof this)throw new TypeError("Promises must be constructed via new");if("function"!=typeof e)throw new TypeError("not a function");this._state=0,this._handled=!1,this._value=void 0,this._deferreds=[],s(e,this)}function i(e,n){for(;3===e._state;)e=e._value;return 0===e._state?void e._deferreds.push(n):(e._handled=!0,void o._immediateFn(function(){var t=1===e._state?n.onFulfilled:n.onRejected;if(null===t)return void(1===e._state?r:u)(n.promise,e._value);var o;try{o=t(e._value)}catch(i){return void u(n.promise,i)}r(n.promise,o)}))}function r(e,n){try{if(n===e)throw new TypeError("A promise cannot be resolved with itself.");if(n&&("object"==typeof n||"function"==typeof n)){var i=n.then;if(n instanceof o)return e._state=3,e._value=n,void f(e);if("function"==typeof i)return void s(t(i,n),e)}e._state=1,e._value=n,f(e)}catch(r){u(e,r)}}function u(e,n){e._state=2,e._value=n,f(e)}function f(e){2===e._state&&0===e._deferreds.length&&o._immediateFn(function(){e._handled||o._unhandledRejectionFn(e._value)});for(var n=0,t=e._deferreds.length;n<t;n++)i(e,e._deferreds[n]);e._deferreds=null}function c(e,n,t){this.onFulfilled="function"==typeof e?e:null,this.onRejected="function"==typeof n?n:null,this.promise=t}function s(e,n){var t=!1;try{e(function(e){t||(t=!0,r(n,e))},function(e){t||(t=!0,u(n,e))})}catch(o){if(t)return;t=!0,u(n,o)}}var a=setTimeout;o.prototype["catch"]=function(e){return this.then(null,e)},o.prototype.then=function(e,t){var o=new this.constructor(n);return i(this,new c(e,t,o)),o},o.all=function(e){var n=Array.prototype.slice.call(e);return new o(function(e,t){function o(r,u){try{if(u&&("object"==typeof u||"function"==typeof u)){var f=u.then;if("function"==typeof f)return void f.call(u,function(e){o(r,e)},t)}n[r]=u,0===--i&&e(n)}catch(c){t(c)}}if(0===n.length)return e([]);for(var i=n.length,r=0;r<n.length;r++)o(r,n[r])})},o.resolve=function(e){return e&&"object"==typeof e&&e.constructor===o?e:new o(function(n){n(e)})},o.reject=function(e){return new o(function(n,t){t(e)})},o.race=function(e){return new o(function(n,t){for(var o=0,i=e.length;o<i;o++)e[o].then(n,t)})},o._immediateFn="function"==typeof setImmediate&&function(e){setImmediate(e)}||function(e){a(e,0)},o._unhandledRejectionFn=function(e){"undefined"!=typeof console&&console&&console.warn("Possible Unhandled Promise Rejection:",e)},o._setImmediateFn=function(e){o._immediateFn=e},o._setUnhandledRejectionFn=function(e){o._unhandledRejectionFn=e},"undefined"!=typeof module&&module.exports?module.exports=o:e.Promise||(e.Promise=o)}(this);


