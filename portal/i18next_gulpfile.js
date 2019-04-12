/*
 * prerequisites:
 * nodeJS virtual environment install via pip nodeenv
 * install NPM (node package manager)
 * install all required modules (i.e. run npm install in the directory containing package.json)
 * run gulp --gulpfile i18next_gulpfile.js will perform default task -
 * which will perform text extraction and translate resulting json to pot file
 * run gulp --gulpfile i18next_gulpfile.js [task name]  will run individual task
 * NB:  should NOT run this in Production environment, the resulting modules in node_modules/ folder from running `npm install` should never be checked in
 */
var gulp = require("gulp");
var source = require("vinyl-source-stream");
var request = require("request");
var merge = require("merge2");
var buffer = require("gulp-buffer");
var del = require("del");
var scanner = require("i18next-scanner");
var concatPo = require("gulp-concat-po");
var merge_json = require("gulp-merge-json");
var using = require("gulp-using");
const path = require("path");
const fs = require("fs");
const i18nextConv = require("i18next-conv");
/*
 * where the generated json/pot files from extraction of js files will reside
 */
const translationSourceDir = path.join(__dirname, "./translations/js/src/");
/*
 * the path to the converted json file from po file of corresponding locale
 * JS files will consume the translated text from here
 * note json files are saved for each specific locale
 */
const translationDestinationDir = path.join(__dirname,"./static/files/locales/");

/*
 * namespace
 */
const nameSpace = "frontend";
const epromsNameSpace = "eproms";
const truenthNameSpace = "gil";
const srcPotFileName = translationSourceDir+nameSpace+".pot";
const epromsSrcPotFileName =  translationSourceDir+epromsNameSpace+".pot";
const truenthSrcPotFileName = translationSourceDir+truenthNameSpace+".pot";

/*
 * JS source directory
 */
const jsSrcPath = "./static/js/src/";

/*
 * helper function for writing file
 */
function save(target) {
  return result => {
    fs.writeFileSync(target, result);
  };
};

/*
 * i18next scanner helper function
 */
function i18nextScanner(files, outputFileName) {
  return gulp.src(files)
               .pipe(scanner({
                    keySeparator: "|",
                    nsSeparator: "|",
                    attr: {
                        list: ["data-i18n"],
                        extensions: [".js", ".html", ".htm"]
                    },
                    func: {
                        list: ["i18next.t", "i18n.t"],
                        extensions: [".js", ".jsx", ".html", ".htm"]
                    },
                    resource: {
                        //the source path is relative to current working directory as specified in the destination folder
                        savePath: outputFileName
                    },
                    interpolation: {
                        prefix: "{",
                        suffix: "}"
                    }
                }))
              .pipe(gulp.dest("translations/js"));
};

/*
 * helper function for writing json file from source po file to specified destination
 */
function writeJsonFileFromPoFile(locale, messageFilePath, outputFileName) {
  let existed = fs.existsSync(messageFilePath);
  if (existed) {
    /*
     * write corresponding json file from source po file
     */
    try {
      console.log("source file, " + messageFilePath + ", found for locale: ", locale);
      i18nextConv.gettextToI18next(locale, fs.readFileSync(messageFilePath), false)
      .then(save(outputFileName));
    } catch(e) {
      console.log("Error occurred writing json from po file: ", messageFilePath);
    };
  };
};

/*
 * extracting text from common js/html files into json file
 */
gulp.task("i18next-extraction", ["clean-src"], function() {
  console.log("extracting text and generate json file ...");
  return i18nextScanner([jsSrcPath+"*.{js,html}", jsSrcPath+"components/*.{js,html}", jsSrcPath+"mixins/*.{js,html}", jsSrcPath+"modules/*.{js,html}", jsSrcPath+"data/common/*.{js,html}", "templates/*.html"], "./src/" + nameSpace + ".json");
});


/*
 * extracting text from  Eproms js/html files into json file
 */
gulp.task("i18next-extraction-eproms", ["clean-eproms-src"], function() {
  console.log("extracting text and generate json file ...");
  return i18nextScanner(["eproms/templates/eproms/*.html", jsSrcPath+"data/eproms/*.{js,html}"], "./src/" + epromsNameSpace + ".json");
});


/*
 * extracting text from TrueNTH js/html files into json file
 */
gulp.task("i18next-extraction-truenth", ["clean-truenth-src"], function() {
  console.log("extracting text and generate json file ...");
  return i18nextScanner(["gil/templates/gil/*.html", jsSrcPath+"data/gil/*.{js,html}"], "./src/" + truenthNameSpace + ".json");
});

/*
 * convert eproms json to pot (the definition file) for translator's consumption
 */
gulp.task("i18nextConvertEpromsJSONToPOT", ["i18next-extraction-eproms"], function() {

  const options = {/* you options here */}
  /*
  * converting json to pot
  */
  console.log("converting Eproms JSON to POT...");
  return i18nextConv.i18nextToPot("en", fs.readFileSync(translationSourceDir+epromsNameSpace+".json"), options).then(save(epromsSrcPotFileName));

});

/*
 * convert TrueNTH json to pot (the definition file) for translator's consumption
 */
gulp.task("i18nextConvertTruenthJSONToPOT", ["i18next-extraction-truenth"], function() {

  const options = {/* you options here */}
  /*
  * converting json to pot
  */
  console.log("converting gil JSON to POT...");
  return i18nextConv.i18nextToPot("en", fs.readFileSync(translationSourceDir+truenthNameSpace+".json"), options).then(save(truenthSrcPotFileName));

});

/*
 * convert common json file to pot (the definition file) for translator's consumption
 */
gulp.task("i18nextConvertJSONToPOT", ["i18next-extraction"], function() {

  const options = {/* you options here */}

  /*
    * converting json to pot
  */
  console.log("converting common JSON to POT...");
  return i18nextConv.i18nextToPot("en", fs.readFileSync(translationSourceDir+nameSpace+".json"), options).then(save(srcPotFileName));

});

/*
 * combine newly created pot file to existing messages.pot file ???
 * do we need this step??
 */
gulp.task("combineAllPotFiles", ["i18nextConvertJSONToPOT"], function() {
    console.log("combine all pot files ...")
    return gulp.src([srcPotFileName, "translations/messages.pot"])
          .pipe(concatPo("messages.pot"))
          .pipe(gulp.dest("translations"));
});

/*
 * converting po to json files
 * note translating existing po file to json, which will be consumed by the front end
 * this task assumes that:
 *    1. text has been extracted from js file into JSON file
 *    2. translated JSON into POT
 *    3. Po files have been returned from translator after uploading POT file from #2
 */
gulp.task("i18nextConvertPOToJSON", ["clean-dest"], function() {
  console.log("converting po to json ...");
  const options = {/* you options here */}
   /*
    * translating po file to json for supported languages
    */
  var __path = path.join(__dirname,"./translations");
  return fs.readdir(__path, function(err, files) {
      files.forEach(function(file) {
        //skip js directory - as it contains original translation json file
        if (file.toLowerCase() !== "js") {
          let filePath = __path + "/" + file;
          fs.stat(filePath, function(err, stat) {
              if (stat.isDirectory()) {
                /*
                 * directories are EN_US, EN_AU, etc.
                 * so check to see if each has a PO file
                 */
                let destDir = translationDestinationDir+(file.replace("_", "-"));

                if (!fs.existsSync(destDir)){
                  fs.mkdirSync(destDir);
                };

                ["messages", "frontend", "eproms", "gil"].forEach(function(source) {
                    /*
                     * write corresponding json file from each po file
                     */
                    writeJsonFileFromPoFile(file, __path+"/"+file+"/LC_MESSAGES/"+source+".po", destDir+"/"+source+".json");
                });
              };
          });
        }
      });
  });
});


/*
 * combining each json file in each locale folder into one file, namely, the translation.json file, to be consumed by the frontend
 * NOTE this task will need to be run after i18nextConvertPOToJSON task, which creates json files from po files
 */
gulp.task("combineTranslationJsons", function() {
  console.log("combining json files ...");
  const options = {/* you options here */}
   /*
    * translating po file to json for supported languages
    */
  var __path = path.join(__dirname,"./translations");
  return fs.readdir(__path, function(err, files) {
      files.forEach(function(file) {
          let filePath = __path + "/" + file;
          fs.stat(filePath, function(err, stat) {
              if (stat.isDirectory()) {
                /*
                 * directories are EN_US, EN_AU, etc.
                 */
                let destDir = translationDestinationDir+(file.replace("_", "-"));

                /*
                 * merge json files into one for frontend to consume
                 * note this plug-in will remove duplicate entries
                 * not this will not delete the original json files that were merged
                 */
                  console.log("merge json files...");
                  console.log("destination directory: " + destDir);
                  try {
                    gulp.src(destDir +"/*.json")
                      .pipe(using({}))
                      .pipe(merge_json({
                        fileName: "translation.json"
                      }))
                      .pipe(gulp.dest(destDir));
                  } catch(e) {
                    console.log("Error occurred merging files " + e.message);
                  };

              };
          });
      });
  });
});

/*
 * clean eproms source file
 */
gulp.task("clean-eproms-src", function() {
  console.log("delete source file...");
  return del([translationSourceDir + epromsNameSpace + ".json"]);
});


/*
 * clean truenth source file
 */
gulp.task("clean-truenth-src", function() {
  console.log("delete source file...");
  return del([translationSourceDir + truenthNameSpace + ".json"]);
});

/*
 * clean common source file
 */
gulp.task("clean-src", function() {
  console.log("delete source file...");
  return del([translationSourceDir + nameSpace + ".json"]);
});

/*
 * clean all generated destination json files
 */
gulp.task("clean-dest", function() {
  console.log("delete json files...");
  return del([translationDestinationDir + "*/*.json"]);
});

/*
 * convert eproms translation json file to pot file
 */
gulp.task("eproms", ["i18nextConvertEpromsJSONToPOT"], function() {
  console.log("Running eproms translation task...");
});

/*
 * convert truenth translation json file to pot file
 */
gulp.task("gil", ["i18nextConvertTruenthJSONToPOT"], function() {
  console.log("Running gil translation task...");
});


/*
 * NOTE, the task - converting po to json file is not included, as I think we need to upload pot to smartling first to have
   it return the po files
   so probably should run "i18nextConvertPOToJSON" task separately
 */
gulp.task("default", ["i18nextConvertJSONToPOT"], function() {
    console.log("running default task..");
});