var tnthDates =  { /*global i18next */
    /** validateDateInputFields  check whether the date is a sensible date in month, day and year fields.
     ** params: month, day and year fields and error field ID
     ** NOTE this can replace the custom validation check; hook this up to the onchange/blur event of birthday field
     ** work better in conjunction with HTML5 native validation check on the field e.g. required, pattern match  ***/
    "validateDateInputFields": function(m, d, y, errorFieldId) {
        m = parseInt(m);
        d = parseInt(d);
        y = parseInt(y);
        var errorField = $("#" + errorFieldId);
        if (!m || !d || !/\d{4}/.test(y)) {  /* prevent premature validation until year has been entered */
            errorField.html("");
            return false;
        }
        if (!(isNaN(m)) && !(isNaN(d)) && !(isNaN(y))) {
            var today = new Date();
            var date = new Date(y, m - 1, d);
            if (!(date.getFullYear() === y && (date.getMonth() + 1) === m && date.getDate() === d)) { // Check to see if this is a real date
                errorField.html(i18next.t("Invalid date. Please try again.")).show();
                return false;
            } else if (date.setHours(0, 0, 0, 0) > today.setHours(0, 0, 0, 0)) {
                errorField.html(i18next.t("Date must not be in the future. Please try again.")).show();
                return false; //shouldn't be in the future
            } else if (y < 1900) {
                errorField.html(i18next.t("Date must not be before 1900. Please try again.")).show();
                return false;
            }
            errorField.html("").hide();
            return true;
        }
        return false;
    },
    /**
     * Simply swaps: a/b/cdef to b/a/cdef (single & double digit permutations accepted...)
     * Does not check for valid dates on input or output!
     * @param currentDate string eg 7/4/1976
     * @returns string eg 4/7/1976
     */
    "swap_mm_dd": function(currentDate) {
        var splitDate = currentDate.split("/");
        return splitDate[1] + "/" + splitDate[0] + "/" + splitDate[2];
    },
    "convertMonthNumeric": function(month) { //Convert month string to numeric
        if (!month) { return ""; }
        else {
            var month_map = {"jan": 1,"feb": 2,"mar": 3,"apr": 4,"may": 5,"jun": 6,"jul": 7,"aug": 8,"sep": 9,"oct": 10,"nov": 11,"dec": 12};
            var m = month_map[month.toLowerCase()];
            return m ? m : "";
        }
    },
    "convertMonthString": function(month) { //Convert month string to text
        if (!month) {
            return "";
        } else {
            var numeric_month_map = {1: "Jan",2: "Feb",3: "Mar",4: "Apr",5: "May",6: "Jun",7: "Jul",8: "Aug",9: "Sep",10: "Oct",11: "Nov",12: "Dec"};
            var m = numeric_month_map[parseInt(month)];
            return m ? m : "";
        }
    },
    "isDate": function(obj) {
        return Object.prototype.toString.call(obj) === "[object Date]" && !isNaN(obj.getTime());
    },
    "displayDateString": function(m, d, y) {
        var s = "";
        s += (d ? d : "");
        if (m) {
            s += (s ? " " : "") + this.convertMonthString(m);
        }
        if (y) {
            s += (s ? " " : "") + y;
        }
        return s;
    },
    /***
     * Calculates number of days between two dates. Used in mPOWEr for surgery/discharge
     * @param startDate - required. Assumes YYYY-MM-DD. This is typically the date of surgery or discharge
     * @param dateToCalc - optional. If empty, then assumes today's date
     * @returns number of days
     */
    "getDateDiff": function(startDate, dateToCalc) {
        if (!startDate) {
            return 0;
        }
        var a = startDate.split(/[^0-9]/);
        var dateTime = new Date(a[0], a[1] - 1, a[2]).getTime();
        var d;
        if (dateToCalc) {
            var c = dateToCalc.split(/[^0-9]/);
            d = new Date(c[0], c[1] - 1, c[2]).getTime();
        } else { // If no baseDate, then use today to find the number of days between dateToCalc and today
            d = new Date().getTime();
        }
        return Math.floor((d - dateTime) / (1000 * 60 * 60 * 24)); // Round down to floor so we don't add an extra day if session is 12+ hours into the day
    },
    "isValidDefaultDateFormat": function(date, errorField) {
        if (!date || date.length < 10) { return false; }
        var dArray = $.trim(date).split(" ");
        if (dArray.length < 3) { return false; }
        var day = parseInt(dArray[0])+"", month = dArray[1], year = dArray[2];
        if (day.length < 1 || month.length < 3 || year.length < 4) { return false; }
        if (!/(0)?[1-9]|1\d|2\d|3[01]/.test(day)) { return false; }
        if (!/jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec/i.test(month)) { return false; }
        if (!/(19|20)\d{2}/.test(year)) { return false; }
        var dt = new Date(date);
        if (!this.isDateObj(dt)) { return false; }
        else if (!this.isValidDate(year, this.convertMonthNumeric(month), day)) {
            return false;
        } else {
            var today = new Date(),
                errorMsg = "";
            if (dt.getFullYear() < 1900) { errorMsg = "Year must be after 1900"; }
            // Only allow if date is before today
            if (dt.setHours(0, 0, 0, 0) > today.setHours(0, 0, 0, 0)) {
                errorMsg = "The date must not be in the future.";
            }
            if (errorMsg) {
                $(errorField).text(errorMsg);
                return false;
            } else {
                $(errorField).text("");
                return true;
            }
        }
    },
    "isDateObj": function(d) {
        return Object.prototype.toString.call(d) === "[object Date]" && !isNaN(d.getTime());
    },
    "isValidDate": function(y, m, d) {
        var date = this.getDateObj(y, m, d), convertedDate = this.getConvertedDate(date), givenDate = this.getGivenDate(y, m, d);
        return String(givenDate) === String(convertedDate);
    },
    /*
     * method does not check for valid numbers, will return NaN if conversion failed
     */
    "getDateObj": function(y, m, d, h, mi, s) {
        h = h || 0;
        mi = mi || 0;
        s = s || 0;
        return new Date(parseInt(y), parseInt(m) - 1, parseInt(d), parseInt(h), parseInt(mi), parseInt(s));
    },
    "getConvertedDate": function(dateObj) {
        if (dateObj && this.isDateObj(dateObj)) { return "" + dateObj.getFullYear() + (dateObj.getMonth() + 1) + dateObj.getDate(); }
        else { return ""; }
    },
    "getGivenDate": function(y, m, d) {
        return "" + y + m + d;
    },
    /*
     *  given a UTC date string, converted to locale/language sensitive date string
     */
    "setUTCDateToLocaleDateString": function(utcDateString, params) {
        if (!utcDateString) {
            return "";
        }
        var dateObj = new Date(utcDateString);
        if (!this.isDateObj(dateObj)) {
            return utcDateString; //return date string as is without re-formattiing
        }
        if (!params) {
            params = { //date format parameters
                day: "numeric",
                month: "short",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit"
            };
        }
        var reformattedLocaleDateString = new Date(dateObj.toUTCString().slice(0, -4));
        reformattedLocaleDateString = reformattedLocaleDateString.toLocaleDateString("en-GB", params); //native Javascript date function, https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Date/toLocaleDateString
        return reformattedLocaleDateString;
    },
    "isSystemDate": function(dateString) {
        /* IOS (8601) date format test */
        /**
         * RegExp to test a string for a full ISO 8601 Date
         * Does not do any sort of date validation, only checks if the string is according to the ISO 8601 spec.
         *  YYYY-MM-DDThh:mm:ss
         *  YYYY-MM-DDThh:mm:ssTZD
         *  YYYY-MM-DDThh:mm:ss.sTZD
         * @see: https://www.w3.org/TR/NOTE-datetime
         * @type {RegExp}
         */
        var IOSDateTest = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(([+-](\d)?\d:\d\d)|Z)?$/i;
        return IOSDateTest.test(dateString);
    },
    "formatDateString": function(dateString, format) { //NB For dateString in ISO-8601 format date as returned from server e.g. '2011-06-29T16:52:48'
        if (dateString) {
            var d = new Date(dateString);
            var day, month, year, hours, minutes, seconds, nd;
             /* IOS (8601) date format test */
            if (this.isSystemDate(dateString)) {
                //IOS date, no need to convert again to date object, just parse it as is
                //issue when passing it into Date object, the output date is inconsistent across from browsers
                var dArray = $.trim($.trim(dateString).replace(/[\.TZ:\-]/gi, " ")).split(" ");
                year = dArray[0];
                month = dArray[1];
                day = dArray[2];
                hours = dArray[3] || "0";
                minutes = dArray[4] || "0";
                seconds = dArray[5] || "0";
            } else {
                if (!this.isDateObj(d)) { //note instantiating ios formatted date using Date object resulted in error in IE
                    return dateString; //return dateString as is without any parsing
                }
                day = d.getDate();
                month = d.getMonth() + 1;
                year = d.getFullYear();
                hours = d.getHours();
                minutes = d.getMinutes();
                seconds = d.getSeconds();
                nd = "";
            }
            var pad = function(n) {n = parseInt(n); return (n < 10) ? "0" + n : n;};
            day = pad(day);
            month = pad(month);
            hours = pad(hours);
            minutes = pad(minutes);
            seconds = pad(seconds);

            switch (format) {
            case "mm/dd/yyyy":
                nd = month + "/" + day + "/" + year;
                break;
            case "mm-dd-yyyy":
                nd = month + "-" + day + "-" + year;
                break;
            case "mm-dd-yyyy hh:mm:ss":
                nd = month + "-" + day + "-" + year + " " + hours + ":" + minutes + ":" + seconds;
                break;
            case "dd/mm/yyyy":
                nd = day + "/" + month + "/" + year;
                break;
            case "mm/dd/yyyy hh:mm:ss":
                nd = month + "/" + day + "/" + year + " " + hours + ":" + minutes + ":" + seconds;
                break;
            case "dd/mm/yyyy hh:mm:ss":
                nd = day + "/" + month + "/" + year + " " + hours + ":" + minutes + ":" + seconds;
                break;
            case "dd-mm-yyyy":
                nd = day + "-" + month + "-" + year;
                break;
            case "dd-mm-yyyy hh:mm:ss":
                nd = day + "-" + month + "-" + year + " " + hours + ":" + minutes + ":" + seconds;
                break;
            case "iso-short":
            case "yyyy-mm-dd":
                nd = year + "-" + month + "-" + day;
                break;
            case "iso":
            case "yyyy-mm-dd hh:mm:ss":
                nd = year + "-" + month + "-" + day + " " + hours + ":" + minutes + ":" + seconds;
                break;
            case "system":
                nd = year + "-" + month + "-" + day + "T" + hours + ":" + minutes + ":" + seconds + "Z";
                break;
            case "d M y hh:mm:ss":
                nd = this.displayDateString(month, day, year);
                nd = nd + " " + hours + ":" + minutes + ":" + seconds;
                break;
            case "d M y":
                nd = this.displayDateString(month, day, year);
                break;
            default:
                nd = this.displayDateString(month, day, year);
                break;
            }
            return nd;
        } else {
            return "";
        }
    },
    "localeSessionKey": "currentUserLocale",
    "clearSessionLocale": function() {
        sessionStorage.removeItem(this.localeSessionKey);
    },
    "convertToLocalTime": function(dateString) {
        var convertedDate = "";
        if (dateString) { //assuming dateString is UTC date/time
            var d = new Date(dateString);
            var newDate = new Date(d.getTime() + d.getTimezoneOffset() * 60 * 1000);
            var offset = d.getTimezoneOffset() / 60;
            var hours = d.getHours();
            newDate.setHours(hours - offset);
            var options = {year: "numeric", day: "numeric", month: "short", hour: "numeric", minute: "numeric", second: "numeric", hour12: false};
            convertedDate = newDate.toLocaleString(options);
        }
        return convertedDate;
    },
    getDateWithTimeZone: function(dObj, format) {
        /*
         * param is a date object - calculating UTC date using Date object's timezoneOffset method
         * the method return offset in minutes, so need to convert it to miliseconds - adding the resulting offset will be the UTC date/time
         */
        if (!dObj) return "";
        format = format || "system";
        if (!this.isDateObj(dObj)) dObj = new Date(dObj);
        var utcDate = new Date(dObj.getTime() + (dObj.getTimezoneOffset()) * 60 * 1000);
        return this.formatDateString(utcDate, format);  //I believe this is a valid python date format, will save it as GMT date/time NOTE, conversion already occurred, so there will be no need for backend to convert it again
    },
    getTodayDateObj: function() { //return object containing today's date/time information
        var today = new Date();
        var td = today.getDate(), tm = today.getMonth() + 1, ty = today.getFullYear();
        var th = today.getHours(), tmi = today.getMinutes(), ts = today.getSeconds();
        var gmtToday = this.getDateWithTimeZone(this.getDateObj(ty, tm, td, th, tmi, ts));
        var pad = function(n) {n = parseInt(n); return (n < 10) ? "0" + n : n;};
        return {
            date: today,
            day: td,
            month: tm,
            year: ty,
            hour: th,
            minute: tmi,
            second: ts,
            displayDay: pad(td),
            displayMonth: pad(tm),
            displayYear: pad(ty),
            displayHour: pad(th),
            displayMinute: pad(tmi),
            displaySecond: pad(ts),
            gmtDate: gmtToday
        };
    },
    dateValidator: function(day, month, year, restrictToPresent) { //parameters: day, month and year values in numeric, boolean value for restrictToPresent, true if the date needs to be before today, false is the default
        var errorMessage = "";
        if (day && month && year) {
            var iy = parseInt(year), im = parseInt(month), iid = parseInt(day), date = new Date(iy, im - 1, iid);
            if (date.getFullYear() === iy && (date.getMonth() + 1) === im && date.getDate() === iid) { // Check to see if this is a real date
                if (iy < 1900) {
                    errorMessage = i18next.t("Year must be after 1900");
                }
                if (restrictToPresent) { // Only allow if date is before today
                    var today = new Date();
                    if (date.setHours(0, 0, 0, 0) > today.setHours(0, 0, 0, 0)) {
                        errorMessage = i18next.t("The date must not be in the future.");
                    }
                }
            } else {
                errorMessage = i18next.t("Invalid Date. Please enter a valid date.");
            }
        } else {
            errorMessage = i18next.t("Missing value.");
        }
        return errorMessage;
    },
    /*
     * helper method for determining whether a date is greater than or equal to start date and less than end date
     * @param targetDate, a date string or Date object
     * @param startDate, a date string or Date object
     * @param endDate, a date string or Date object
     * @param startDateInclusive, boolean indicating whether comparison against startdate is inclusive,
     * i.e. startDate == targetDate
     * @param endDateInclusive, boolean indicating whether comparison against enddate is inclusive,
     * i.e. endDate == targetDate
     */
    isBetweenDates: function(targetDate, startDate, endDate, startDateInclusive, endDateInclusive) {
        if (!targetDate) return false;
        var d1 = !this.isDateObj(targetDate) ? new Date(targetDate) : targetDate;
        var d2 = !this.isDateObj(startDate) ? new Date(startDate) : startDate;
        var d3 = !this.isDateObj(endDate) ? new Date(endDate) : endDate;
        var startDateComparison = startDateInclusive ? (d1.getTime() >= d2.getTime()) : (d1.getTime() > d2.getTime());
        var endDateComparison = endDateInclusive ? (d1.getTime() <= d3.getTime()) : (d1.getTime() < d3.getTime());
        return startDateComparison && endDateComparison;
    },
    /*
     * helper function for subtracting day(s) from a date string or a Date object
     * @param targetDate, a date string or Date object from which day(s) will be subtracted
     * @param numOfDays, a number representing the number of days
     */
    minusDate: function(targetDate, numOfDays) {
        if (!numOfDays) numOfDays = 0;
        var dateOffset = (24*60*60*1000) * numOfDays; //day in miliseconds
        targetDate = !this.isDateObj(targetDate) ? new Date(targetDate) : targetDate;
        return targetDate.setTime(targetDate.getTime() - dateOffset);
    },
    /*
     * helper function for determing if a target date string or Date object is less than a given comparison date
     * @param targetDate a date string or Date object that is used to determine whether it is less than the comparison date
     * @param comparedDate, a date string or Date object used to compare to target date
     * @param inclusive boolean, determines whether to allow comparison to be inclusive, i.e. targetDate == comparedDate
     */
    isLessThanDate: function(targetDate, comparedDate, inclusive) {
        if (!targetDate) return false;
        var d1 = !this.isDateObj(targetDate) ? new Date(targetDate) : targetDate;
        var d2 = !this.isDateObj(comparedDate) ? new Date(comparedDate) : comparedDate;
        return inclusive ? (d1.getTime() <= d2.getTime()) : (d1.getTime() < d2.getTime());
    },
    /*
     * helper function for determing if a target date string or Date object is greater than a given comparison date
     * @param targetDate a date string or Date object that is used to determine whether it is greater than the comparison date
     * @param comparedDate, a date string or Date object used to compare to target date
     * @param inclusive boolean, determines whether to allow comparison to be inclusive, i.e. targetDate == comparedDate
     */
    isGreaterThanDate: function(targetDate, comparedDate, inclusive) {
        if (!targetDate) return false;
        var d1 = !this.isDateObj(targetDate) ? new Date(targetDate) : targetDate;
        var d2 = !this.isDateObj(comparedDate) ? new Date(comparedDate) : comparedDate;
        return (d1.getTime() > d2.getTime());
    },
    /*
     * helper function that returns local timezone in text
     */
    getTimeZoneDisplay: function() {
        var localTimezone = "";
        try {
            localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        } catch(e) {
            console.log("Intl object not supported ", e);
            localTimezone = "";
        }
        if (localTimezone) return localTimezone;
        return new Date().toLocaleDateString(undefined, {day:"2-digit",timeZoneName: "long" }).substring(4);
    }
};
export default tnthDates;
export var validateDateInputFields = tnthDates.validateDateInputFields; /* generic validation function for global use */
