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
  setTimeout('$("#tnthNavWrapper").css("visibility","visible")', 100);

});

var userSetLang = 'en_US';// FIXME scope? defined in both tnth.js/banner and main.js

