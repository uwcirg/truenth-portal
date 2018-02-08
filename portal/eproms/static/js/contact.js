$(document).ready(function(){
    $("#profileForm").validator({disable: false});
    $("#submitButton").on("click", function(e) {
        e.preventDefault();
        var formData = {};
        $("#contactForm").find("input, select, textarea").each(function() {
            formData[$(this).attr("name")] = $(this).val() || $(this).text();
        });
        if (formData.sendername && formData.body && formData.email) {
          var self = $(this), loadingIndicator = $(".contact-loading-indicator");
          self.hide();
          loadingIndicator.show();
          $.ajax({
              data: formData,
              type: "POST",
              url: "/contact",
              dataType: "json",
              success: function(response) {
                  var msgid = response["msgid"];
                  $("#contactForm .post-contact-response").html("");
                  setTimeout(function() {
                    self.show();
                    loadingIndicator.hide();
                    document.location = "/contact/" + String(msgid);
                  }, 1000);
              },
              error: function(response) {
                  var msg = $("<div></div>").html(response.responseText);
                  var error = $("p", msg).text()
                  $("#contactForm .post-contact-response").html(error);
                  self.show();
                  loadingIndicator.hide();
              }
          });
      } else {
          $("#contactForm .post-contact-response").html($("#noResponseText").text());
      }
    });
  });