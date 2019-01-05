module.exports = {
    "env": {
        "browser": true
    },
    "parserOptions": {
        "ecmaVersion": 6,
        "sourceType": "module"
    },
    "extends": "eslint:recommended",
    "rules": {
        "indent": [
            "error",
            4
        ],
        "linebreak-style": [
            "error",
            "unix"
        ],
        "quotes": [
            "error",
            "double"
        ],
        "semi": [
            "error",
            "always"
        ],
        "eqeqeq": 2,
        "complexity": [2, 4],
        "curly": 2,
        "no-undef": 2,
        "no-use-before-define": 2,
        "guard-for-in": 2,
        "no-unused-expressions": 2
    }
};

