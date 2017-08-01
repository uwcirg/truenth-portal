/*
 * SAMPLE gulp tasks ran in local instance to extract phrase in to json
 * then convert json to POT file for submission to translator (see convert.js)
 *
 */

var gulp = require('gulp');
var scanner = require('i18next-scanner');
var c = require('./convert.js');
 
gulp.task('i18next', function() {
    return gulp.src(['src/**/*.{js,html}']) 
        .pipe(scanner({
            lngs: ['en', 'de'], // supported languages 
            keySeparator: '|',
            nsSeparator: '|',
            resource: {
                // the source path is relative to current working directory 
                loadPath: 'locales/{{lng}}/translation.json',
                
                // the destination path is relative to your `gulp.dest()` path 
                savePath: 'locales/{{lng}}/translation.json'
            }
        }))
        .pipe(gulp.dest('dest'));
});

gulp.task('i18convert', function() {
    c.convert('en');
});
