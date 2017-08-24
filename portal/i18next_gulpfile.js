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
var gulp = require('gulp');
var source = require('vinyl-source-stream');
var request = require('request');
var merge = require('merge2');
var concat = require('gulp-concat');
var buffer = require('gulp-buffer');
var del = require('del');
var uglify = require('gulp-uglify');
var rename = require('gulp-rename');
var scanner = require('i18next-scanner');
var concatPo = require('gulp-concat-po');
const path = require('path');
const fs = require('fs');
const i18nextConv = require('i18next-conv');
/*
 * where the generated json/pot files from extraction of js files will reside
 */
const translationSourceDir = path.join(__dirname, './translations/js/src/');
/*
 * the path to the converted json file from po file of corresponding locale
 * JS files will consume the translated text from here
 * note json files are saved for each specific locale
 */
const translationDestinationDir = path.join(__dirname,'./static/files/locales/');
/*
 * supported languages
 */
const languagesArray = ['en-US', 'en-AU'];
/*
 * namespace
 */
const nameSpace = "translation";

/*
 * helper function for writing file
 */
function save(target) {
  return result => {
    fs.writeFileSync(target, result);
  };
};

/*
 * extracting text from js/html files into json file
 */
gulp.task('i18next-extraction', function() {
    console.log("extracting text and generate json file ...")
    del(['translations/js/src/translation.json']);
    return gulp.src(['static/**/*.{js,html}'])
               .pipe(scanner({
                    lngs: languagesArray, // supported languages
                    keySeparator: "|",
                    nsSeparator: "|",
                    attr: {
                        list: ['data-i18n'],
                        extensions: ['.js', '.html', '.htm']
                    },
                    func: {
                        list: ['i18next.t', 'i18n.t'],
                        extensions: ['.js', '.jsx']
                    }
                    ,
                    resource: {
                        //the source path is relative to current working directory as specified in the destination folder
                        savePath: './src/' + nameSpace + '.json'
                    }
                }))
              .pipe(gulp.dest('translations/js'));
});

/*
 * convert json to pot (the definition file) for translator's consumption
 */
gulp.task('i18nextConvertJSONToPOT', ['i18next-extraction'], function() {

    const options = {/* you options here */}
   /*
    * converting json to pot
    */
    console.log("converting JSON to POT...");
    del(['translations/js/src/translation.pot']);
    i18nextConv.i18nextToPot('en', fs.readFileSync(translationSourceDir+nameSpace+".json"), options).then(save(translationSourceDir+nameSpace+".pot"));

});

/*
 * combine newly created pot file to existing messages.pot file ???
 * do we need this step??
 */
gulp.task('combineAllPotFiles', ['i18nextConvertJSONToPOT'], function() {
    console.log("combine all pot files ...")
    return gulp.src([translationSourceDir+nameSpace+".pot", 'translations/messages.pot'])
          .pipe(concatPo('messages.pot'))
          .pipe(gulp.dest('translations'));
});

/*
 * converting po to json files
 * note translating existing po file to json, which will be consumed by the front end
 * this task assumes that:
 *    1. text has been extracted from js file into JSON file
 *    2. translated JSON into POT
 *    3. merged new POT into main POT file [need to check about this step]
 *    4. Po files have been returned from translator after uploading POT file from #3
 */
gulp.task('i18nextConvertPOToJSON', function() {
  console.log("converting po to json ...")
  const options = {/* you options here */}

  del(['static/files/**/translation.json']);

   /*
    * translating po file to json for supported languages
    */
  languagesArray.forEach(function(lng) {
      var destination = translationDestinationDir+lng+"/translation.json";
      fs.open(destination, 'w+', function(err, fd) {
        if (err) console.log("error occurred writing " + lng + " json: " + err);
        else {
          i18nextConv.gettextToI18next(lng, fs.readFileSync(path.join(__dirname,'./translations/' + lng.replace('-', '_') + '/LC_MESSAGES/messages.po')), options)
          .then(save(destination));
          fs.close(fd, function(err) {
              if (err) console.log("error occurred closing " + destination);
          });
        };
      });
  });
});

/*
 * concating all necessary i18next JS files into one
 * don't run this unless files have been changed
 */
gulp.task('i18nextConcatScripts', function() {
  console.log("concat i18next scripts ...")
  var i18nextMain = request('https://unpkg.com/i18next/i18next.js')
    .pipe(source('i18nextMain.js'));
  var i18nextXHRBackend = request('https://unpkg.com/i18next-xhr-backend/i18nextXHRBackend.js')
    .pipe(source('i18nextXHRBackend.js'));
  var i18nextLnDetection = request('https://unpkg.com/i18next-browser-languagedetector/i18nextBrowserLanguageDetector.js')
    .pipe(source('i18nextBrowserLanguageDetector.js'));

  return merge(i18nextMain, i18nextXHRBackend, i18nextLnDetection)
    .pipe(buffer())
    .pipe(concat('i18next.js'))
    .pipe(gulp.dest('static/js'));
});

/*
 * minify combined i18next JS file
 * don't run this unless files have been changed
 */
gulp.task("minifyi18nextScripts", ["i18nextConcatScripts"], function() {
  console.log("minify i18next scripts ...")
  del(['static/js/i18next*.js']);
  return gulp.src("static/js/i18next.js")
    .pipe(uglify())
    .pipe(rename('i18next.min.js'))
    .pipe(gulp.dest('static/js'));
});

/*
 * clean all generated files
 */
gulp.task('clean', function() {
  del(['static/files/**/translation.json', 'translations/js/src/*']);
});

/*
 * NOTE, the task - converting po to json file is not included, as I think we need to upload pot to smartling first to have
   it return the po files
   so probably should run 'i18nextConvertPOToJSON' task separately
 */
gulp.task('default', ['i18nextConvertJSONToPOT'], function() {
    console.log('running default task..');
});