/* ========================================================================
 * TrueNTH Portal Nav Functions. For use with portal_wrapper.html
 * Requires jQuery ver 1.10 or above
 * ========================================================================
 * Dropdown based on Bootstrap Dropdown
 * ======================================================================== */

+function ($) {

  'use strict';

  // DROPDOWN CLASS DEFINITION
  // =========================

  var backdrop = '.tnth-dropdown-backdrop'
  var toggle   = '[data-toggle="tnth-dropdown"]'
  var Dropdown = function (element) {
    $(element).on('click.bs.tnth-dropdown', this.toggle)
  }

  Dropdown.VERSION = '3.2.0'

  Dropdown.prototype.toggle = function (e) {
    var $this = $(this)

    if ($this.is('.tnth-disabled, :disabled')) return

    var $parent  = getParent($this)
    var isActive = $parent.hasClass('tnth-open')

    clearMenus()

    if (!isActive) {
      if ('ontouchstart' in document.documentElement && !$parent.closest('.tnth-navbar-xs').length) {
        // if mobile we use a backdrop because click events don't delegate
        $('<div class="tnth-dropdown-backdrop"/>').insertAfter($(this)).on('click', clearMenus)
      }

      var relatedTarget = { relatedTarget: this }
      $parent.trigger(e = $.Event('show.bs.tnth-dropdown', relatedTarget))

      if (e.isDefaultPrevented()) return

      $this.trigger('focus')

      $parent
          .toggleClass('tnth-open')
          .trigger('shown.bs.tnth-dropdown', relatedTarget)
    }

    return false
  }

  Dropdown.prototype.keydown = function (e) {
    if (!/(38|40|27)/.test(e.keyCode)) return

    var $this = $(this)

    e.preventDefault()
    e.stopPropagation()

    if ($this.is('.tnth-disabled, :disabled')) return

    var $parent  = getParent($this)
    var isActive = $parent.hasClass('tnth-open')

    if (!isActive || (isActive && e.keyCode == 27)) {
      if (e.which == 27) $parent.find(toggle).trigger('focus')
      return $this.trigger('click')
    }

    var desc = ' li:not(.divider):visible a'
    var $items = $parent.find('[role="menu"]' + desc + ', [role="listbox"]' + desc)

    if (!$items.length) return

    var index = $items.index($items.filter(':focus'))

    if (e.keyCode == 38 && index > 0)                 index--                        // up
    if (e.keyCode == 40 && index < $items.length - 1) index++                        // down
    if (!~index)                                      index = 0

    $items.eq(index).trigger('focus')
  }

  function clearMenus(e) {
    if (e && e.which === 3) return
    $(backdrop).remove()
    $(toggle).each(function () {
      var $parent = getParent($(this))
      var relatedTarget = { relatedTarget: this }
      if (!$parent.hasClass('tnth-open')) return
      $parent.trigger(e = $.Event('hide.bs.tnth-dropdown', relatedTarget))
      if (e.isDefaultPrevented()) return
      $parent.removeClass('tnth-open').trigger('hidden.bs.tnth-dropdown', relatedTarget)
    })
  }

  function getParent($this) {
    var selector = $this.attr('data-target')

    if (!selector) {
      selector = $this.attr('href')
      selector = selector && /#[A-Za-z]/.test(selector) && selector.replace(/.*(?=#[^\s]*$)/, '') // strip for ie7
    }

    var $parent = selector && $(selector)

    return $parent && $parent.length ? $parent : $this.parent()
  }


  // DROPDOWN PLUGIN DEFINITION
  // ==========================

  function Plugin(option) {
    return this.each(function () {
      var $this = $(this)
      var data  = $this.data('bs.tnth-dropdown')

      if (!data) $this.data('bs.tnth-dropdown', (data = new Dropdown(this)))
      if (typeof option == 'string') data[option].call($this)
    })
  }

  var old = $.fn.dropdown

  $.fn.dropdown             = Plugin
  $.fn.dropdown.Constructor = Dropdown


  // DROPDOWN NO CONFLICT
  // ====================

  $.fn.dropdown.noConflict = function () {
    $.fn.dropdown = old
    return this
  }


  // APPLY TO STANDARD DROPDOWN ELEMENTS
  // ===================================

  $(document)
      .on('click.bs.tnth-dropdown.data-api', clearMenus)
      .on('click.bs.tnth-dropdown.data-api', '.tnth-dropdown form', function (e) { e.stopPropagation() })
      .on('click.bs.tnth-dropdown.data-api', toggle, Dropdown.prototype.toggle)
      .on('keydown.bs.tnth-dropdown.data-api', toggle + ', [role="menu"], [role="listbox"]', Dropdown.prototype.keydown)

}(jQuery);

// Run dropdown
$('.tnth-dropdown-toggle').dropdown();

// Simple show/hide for XS menu
$('.tnth-navbar-toggle').click(function(){
  $('#tnthNavbarXs').slideToggle('fast');
});

$(document).ready(function(){
  // Once nav is loaded, make the wrapper visible
  setTimeout('$("#tnthNavWrapper").css("visibility","visible")', 0);

});
var userSetLang = 'en_US';// FIXME scope? defined in both tnth.js/banner and main.js

sessionMonitor = function(options) {
    "use strict";

    var defaults = {
        // Session lifetime (milliseconds)
        sessionLifetime: 60 * 60 * 1000,
        // Amount of time before session expiration when the warning is shown (milliseconds)
        timeBeforeWarning: 10 * 60 * 1000,
        // Minimum time between pings to the server (milliseconds)
        minPingInterval: 1 * 60 * 1000,
        // Space-separated list of events passed to $(document).on() that indicate a user is active
        activityEvents: 'mouseup',
        // URL to ping the server using HTTP POST to extend the session
        pingUrl: '/api/ping',
        // URL used to log out when the user clicks a "Log out" button
        logoutUrl: '/logout',
        // URL used to log out when the session times out
        timeoutUrl: '/logout?timeout=1',
        ping: function() {
            // Ping the server to extend the session expiration
            $.ajax({
                type: 'POST',
                url: self.pingUrl
            });
        },
        logout: function() {
            // Go to the logout page.
            window.location.href = self.logoutUrl;
        },
        onwarning: function() {
            // Below is example code to demonstrate basic functionality.
            // Use this to warn the user that the session will expire and allow
            // the user to take action.
            // Override this method to customize the warning.
            var warningMinutes = Math.round(self.timeBeforeWarning / 60 / 1000),
                $alert = $('<div id="jqsm-warning">Your session will expire in ' +
                        warningMinutes + ' minutes. ' +
                       '<button id="jqsm-stay-logged-in">Stay Logged In</button>' +
                       '<button id="jqsm-log-out">Log Out</button>' +
                       '</div>');

            if (!$('body').children('div#jqsm-warning').length) {
                $('body').prepend($alert);
            }
            $('div#jqsm-warning').show();
            $('button#jqsm-stay-logged-in').on('click', self.extendsess)
                .on('click', function() { $alert.hide(); });
            $('button#jqsm-log-out').on('click', self.logout);
        },
        onbeforetimeout: function() {
            // By default this does nothing. Override this method to perform
            // actions (such as saving draft data) before the user is
            // automatically logged out.  This may optionally return a
            // jQuery Deferred object, in which case ontimeout will be
            // executed when the deferred is resolved or rejected.
        },
        ontimeout: function() {
            // Go to the timeout page.
            window.location.href = self.timeoutUrl;
        }
    },
    self = {},
    _warningTimeoutID,
    _expirationTimeoutID,
    // The time of the last ping to the server.
    _lastPingTime = 0;

    function extendsess() {
        // Extend the session expiration. Ping the server and reset the
        // timers if the minimum interval has passed since the last ping.
        var now = $.now(),
            timeSinceLastPing = now - _lastPingTime;

        if (timeSinceLastPing > self.minPingInterval) {
            _lastPingTime = now;
            _resetTimers();
            self.ping();
        }
    }

    function _resetTimers() {
        // Reset the session warning and session expiration timers.
        var warningTimeout = self.sessionLifetime - self.timeBeforeWarning;

        window.clearTimeout(_warningTimeoutID);
        window.clearTimeout(_expirationTimeoutID);
        _warningTimeoutID = window.setTimeout(self.onwarning, warningTimeout);
        _expirationTimeoutID = window.setTimeout(_onTimeout, self.sessionLifetime);
    }

    function _onTimeout() {
        // A wrapper that calls onbeforetimeout and ontimeout and supports
        // asynchronous code.
        $.when(self.onbeforetimeout()).always(self.ontimeout);
    }

    // Add default variables and methods, user specified options, and
    // non-overridable public methods to the session monitor instance.
    $.extend(self, defaults, options, {
        extendsess: extendsess
    });
    // Set an event handler to extend the session upon user activity
    // (e.g. mouseup).
    $(document).on(self.activityEvents, extendsess);
    // Start the timers and ping the server to ensure they are in sync
    // with the backend session expiration.
    extendsess();

    return self;
};

// Configure and start the session timeout monitor
sessMon = sessionMonitor({
    sessionLifetime: DEFAULT_SESSION_LIFETIME,
    timeBeforeWarning: 1 * 60 * 1000,
    minPingInterval: 1 * 60 * 1000,  // 1 minute
    onwarning: function() {
        $("#session-warning-modal").modal("show");
    }
});
$(document).ready( function() {
    // Configure the session timeout warning modal
    $("#session-warning-modal")
        .modal({
            "backdrop": "static",
            "keyboard": false,
            "show": false
        })
        .on("click", "#stay-logged-in", sessMon.extendsess)
        .on("click", "#log-out", sessMon.logout)
        .find("#remaining-time").text(sessMon.timeBeforeWarning / 1000);
});
window.sessMon = sessMon;



