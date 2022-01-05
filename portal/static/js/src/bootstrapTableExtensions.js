import {dateSorter, alphanumericSorter} from "./modules/Utility.js";

/*
 * global variables, can be used in custom sort in datatable, e.g. patient list
 */
var tnthTables = window.tnthTables = {
    dateSorter : dateSorter,
    alphanumericSorter: alphanumericSorter
};
/*
 * function used by bootstrap datatable extension lib
 */
var alphanum = window.alphanum = alphanumericSorter;
