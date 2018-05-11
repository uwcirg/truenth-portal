/***
 * Bootstrap datatables functions - Uses http://bootstrap-table.wenzhixin.net.cn/documentation/
 ****/
var tnthTables = {
    /***
     * Quick way to sort when text is wrapper in an <a href> or other tag
     * @param a,b - the two items to compare
     * @returns 1,-1 or 0 for sorting
     */
    "stripLinksSorter": function(a, b) {
        a = $(a).text();
        b = $(b).text();
        var aa = parseFloat(a);
        var bb = parseFloat(b);
        return bb - aa;
    },
    /***
     * Quick way to sort when text is wrapped in an <a href> or other tag - NOTE for text that is NOT number
     * @param a,b - the two items to compare
     * @returns 1,-1 or 0 for sorting
     */
    "stripLinksTextSorter": function(a, b) {
        var aa = $(a).text();
        var bb = $(b).text();
        if (aa < bb) {
            return -1;
        }
        if (aa > bb) {
            return 1;
        }
        return 0;
    },
    /***
     * sorting date string,
     * @param a,b - the two items to compare - note, this assumes that the parameters are in valid date format e.g. 3 August 2017
     * @returns 1,-1 or 0 for sorting
     */
    "dateSorter": function(a, b) {
        a = a || 0;
        b = b || 0;
        /*
         * make sure the string passed in does not have line break element if so it is a possible mult-line text, split it up and use the first item in the resulting array
         */
        var regex = /<br\s*[\/]?>/gi;
        a = a.replace(regex, "\n");
        b = b.replace(regex, "\n");
        var ar = a.split("\n");
        if (ar.length > 0) {
            a = ar[0];
        }
        var br = b.split("\n");
        if (br.length > 0) {
            b = br[0];
        }
        /* note getTime returns the numeric value corresponding to the time for the specified date according to universal time
         * therefore, can be used for sorting
         */
        var a_d = (new Date(a)).getTime();
        var b_d = (new Date(b)).getTime();

        if (isNaN(a_d)) {
            a_d = 0;
        }
        if (isNaN(b_d)) {
            b_d = 0;
        }

        return b_d - a_d;
    },
    /***
     * sorting alpha numeric string
     */
    "alphanumericSorter": function(a, b) {
        /*
         * see https://cdn.rawgit.com/myadzel/6405e60256df579eda8c/raw/e24a756e168cb82d0798685fd3069a75f191783f/alphanum.js
         */
        return alphanum(a, b); /*global alphanum */
    }
};
