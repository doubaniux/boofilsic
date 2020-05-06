$(document).ready( function() {
    $("#submit").click(function(e) {
        e.preventDefault();
        $("#scrapeForm form").submit();
    });

    // assume there  is only one input[file] on page
    $("input[type='file']").each(function() {
        $(this).after('<img src="#" alt="" id="previewImage" style="margin:10px 0; max-width:500px;"/>');
    });
    // preview uploaded pic})
    $("input[type='file']").change(function() {
        if (this.files && this.files[0]) {
            var reader = new FileReader();

            reader.onload = function (e) {
                $('#previewImage').attr('src', e.target.result);
            }

            reader.readAsDataURL(this.files[0]);
        }
    });
});