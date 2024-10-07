/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./templates/**/*.html",
        "./static/**/*.js",
    ],
    purge: {
        enabled: false,
    },
    safelist: [
        'bg-red-500',
        'bg-green-500',
        // Add any other dynamic class names here (or they won't be included in the build!)
    ],
    theme: {
        extend: {
            // Add custom theme configurations here if needed. For example:
            colors: {
                'primary': '#007bff',
            },
        },
    },
    plugins: [require("daisyui")],
    daisyui: {
        themes: [
            "light", "dark", "cupcake", "bumblebee", "emerald", "corporate", "synthwave", "retro", "cyberpunk", "valentine", "halloween", "garden", "forest", "aqua", "lofi", "pastel", "fantasy", "wireframe", "black", "luxury", "dracula", "cmyk", "autumn", "business", "acid", "lemonade"
        ],
        styled: true,
        base: true,
  },
}
