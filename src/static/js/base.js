document.addEventListener("DOMContentLoaded", function() {
    const menuToggle = document.getElementById("menuToggle");
    const sidebar = document.getElementById("sidebar");
    const closeSidebar = document.getElementById("closeSidebar");

    // Open the sidebar when menu button is clicked
    menuToggle.addEventListener("click", function() {
        sidebar.classList.toggle("active");
    });

    // Close the sidebar when close button is clicked
    closeSidebar.addEventListener("click", function() {
        sidebar.classList.remove("active");
    });

    // Profile dropdown functionality
    const profileMenu = document.getElementById("profileMenu");
    const profileDropdown = document.getElementById("profileDropdown");

    // Toggle the profile dropdown on clicking the profile section
    profileMenu.addEventListener("click", function() {
        profileDropdown.classList.toggle("show");
    });

    // Close the dropdown if clicked outside of the profile menu
    window.addEventListener("click", function(event) {
        if (!profileMenu.contains(event.target)) {
            profileDropdown.classList.remove("show");
        }
    });
});
