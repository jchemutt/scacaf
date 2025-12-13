/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.{html,js}",
    "./**/templates/**/*.{html,js}",
    "./knowledge_portal/templates/**/*.html",
    "./knowledge_portal/templates/**/*.js",
    "./portal/**/*.html",
    "./portal/**/*.js",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50:'#eef2ff',100:'#e0e7ff',200:'#c7d2fe',300:'#a5b4fc',
          400:'#818cf8',500:'#6366f1',600:'#4f46e5',700:'#4338ca',
          800:'#3730a3',900:'#312e81',
        },
      },
      boxShadow: {
        soft: '0 8px 30px rgba(0,0,0,.06)',
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
    require("@tailwindcss/typography"),
  ],
};
