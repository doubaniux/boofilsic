$(document).ready( function() {
    // assume there  is only one input[file] on page
    $("input[type='file']").each(function() {
        $(this).after('<img src="#" alt="" id="previewImage" style="margin:10px 0; max-width:500px;"/>');
    })

    // mark required
    $("input[required]").each(function() {
        $(this).prev().prepend("*");
    })
    // preview uploaded pic
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