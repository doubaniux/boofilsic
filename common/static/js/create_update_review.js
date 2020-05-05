$(document).ready( function() {

    $(".markdownx textarea").attr("placeholder", "拖拽图片至编辑框即可插入哦~");

    $(".preview-button").click(function() {
        if ($(".markdownx-preview").is(":visible")) {
            $(".preview-button").text("预览");
            $(".markdownx-preview").hide();
            $(".markdownx textarea").show();
        } else {
            $(".preview-button").text("编辑");
            $(".markdownx-preview").show();
            $(".markdownx textarea").hide();
        }
    });

    let ratingLabels = $("#main .rating-star");
    $(ratingLabels).each( function(index, value) {
        let ratingScore = $(this).data("rating-score") / 2;
        $(this).starRating({
            initialRating: ratingScore,
            readOnly: true,
        });
    });
});