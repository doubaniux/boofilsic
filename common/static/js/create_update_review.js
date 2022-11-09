$(document).ready( function() {
    
    $(".markdownx-preview").hide();
    $(".markdownx textarea").attr("placeholder", "从剪贴板粘贴或者拖拽文件至编辑框即可插入图片");

    $(".review-form__preview-button").on('click', function() {
        if ($(".markdownx-preview").is(":visible")) {
            $(".review-form__preview-button").text("预览");
            $(".markdownx-preview").hide();
            $(".markdownx textarea").show();
        } else {
            $(".review-form__preview-button").text("编辑");
            $(".markdownx-preview").show();
            $(".markdownx textarea").hide();
        }
    });

    let ratingLabels = $(".rating-star");
    $(ratingLabels).each( function(index, value) {
        let ratingScore = $(this).data("rating-score") / 2;
        $(this).starRating({
            initialRating: ratingScore,
            readOnly: true,
        });
    });
    
});