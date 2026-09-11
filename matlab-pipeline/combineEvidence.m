function evidence_result = combineEvidence(lesion_result, grade_result, original_image)
% COMBINEEVIDENCE Rule-based evidence fusion and referral decision synthesizer.
%
% Inputs:
%   lesion_result  - Struct from detectLesions (.ma_mask, .ex_mask, .ma_present, .ex_present)
%   grade_result   - Struct from gradeDR (.grade, .probabilities, .gradcam_map)
%   original_image - HxWx3 uint8 original fundus RGB image
%
% Outputs:
%   evidence_result - Struct with fields:
%                       .overlay_image - HxWx3 uint8 RGB image with blended evidence
%                       .referral      - Boolean referral recommendation
%                       .why_refer     - Plain-language clinical reasoning string
%                       .evidence_list - Cell array of detected evidence strings

    if ischar(original_image) || isstring(original_image)
        original_image = imread(char(original_image));
    end

    [H, W, C] = size(original_image);
    if C == 1
        original_image = cat(3, original_image, original_image, original_image);
    end

    grade = grade_result.grade;
    ma_present = lesion_result.ma_present;
    ex_present = lesion_result.ex_present;

    % 1. Plain-language ICDR Grade Labels
    gradeLabels = {
        'Grade 0: No Diabetic Retinopathy', ...
        'Grade 1: Mild Non-Proliferative DR', ...
        'Grade 2: Moderate Non-Proliferative DR', ...
        'Grade 3: Severe Non-Proliferative DR', ...
        'Grade 4: Proliferative DR'
    };
    gradeStr = gradeLabels{min(max(grade + 1, 1), 5)};

    % 2. Referral Logic (Rule-based: Grade >= 2 AND (MA present OR EX present))
    hasLesions = ma_present || ex_present;
    referral = (grade >= 2) && hasLesions;

    % 3. Plain-Language "Why Refer" String (Built ONLY from DR grade and lesion presence)
    lesionTypes = {};
    if ma_present
        lesionTypes{end+1} = 'microaneurysms';
    end
    if ex_present
        lesionTypes{end+1} = 'hard exudates';
    end

    if isempty(lesionTypes)
        lesionStr = 'no spatial lesions (microaneurysms/exudates)';
    else
        lesionStr = strjoin(lesionTypes, ' and ');
    end

    if referral
        why_refer = sprintf('Referral recommended: Classifier assigned %s (Grade %d >= 2) confirmed by spatial detection of %s.', ...
            gradeStr, grade, lesionStr);
    elseif grade >= 2 && ~hasLesions
        why_refer = sprintf('Referral withheld / re-evaluation advised: Classifier assigned %s (Grade %d >= 2), but no confirming spatial lesions (microaneurysms/exudates) were detected.', ...
            gradeStr, grade);
    elseif grade < 2 && hasLesions
        why_refer = sprintf('Monitoring recommended: Detected %s, but overall severity grade is mild (%s). Immediate specialist referral is not required.', ...
            lesionStr, gradeStr);
    else
        why_refer = sprintf('No referral required: Retinal image displays no significant DR severity (%s) and no detectable lesion activity.', ...
            gradeStr);
    end

    % 4. Build Evidence List
    evidence_list = {};
    evidence_list{end+1} = sprintf('ICDR Severity Classification: %s', gradeStr);
    evidence_list{end+1} = sprintf('Grading Confidence: %.1f%%', max(grade_result.probabilities) * 100);

    if ma_present
        evidence_list{end+1} = 'Microaneurysms (MA) detected in spatial segmentation';
    else
        evidence_list{end+1} = 'No Microaneurysms (MA) detected';
    end

    if ex_present
        evidence_list{end+1} = 'Hard Exudates (EX) detected in spatial segmentation';
    else
        evidence_list{end+1} = 'No Hard Exudates (EX) detected';
    end

    % 5. Alpha-Blend Evidence Overlay
    % Color code Grad-CAM heatmap using jet colormap
    gradcamMap = imresize(grade_result.gradcam_map, [H, W]);
    cmap = jet(256);
    heatmapIdx = uint8(floor(gradcamMap * 255) + 1);
    heatmapRGB = uint8(zeros(H, W, 3));
    for c = 1:3
        channelCmap = cmap(:, c);
        heatmapRGB(:, :, c) = uint8(channelCmap(heatmapIdx) * 255);
    end

    % Alpha blend original image with Grad-CAM heatmap (30% heatmap weight)
    alpha = 0.30;
    blendImg = uint8(double(original_image) * (1 - alpha) + double(heatmapRGB) * alpha);

    % Overlay Lesion Masks: Microaneurysms in RED, Exudates in YELLOW
    maMask = imresize(lesion_result.ma_mask, [H, W], 'nearest');
    exMask = imresize(lesion_result.ex_mask, [H, W], 'nearest');

    % Dilation for visibility on overlay
    se = strel('disk', 2);
    maVisible = imdilate(maMask, se);
    exVisible = imdilate(exMask, se);

    % Red overlay for MA
    R = blendImg(:, :, 1); G = blendImg(:, :, 2); B = blendImg(:, :, 3);
    R(maVisible) = 255; G(maVisible) = 30; B(maVisible) = 30;

    % Yellow overlay for EX
    R(exVisible) = 255; G(exVisible) = 255; B(exVisible) = 0;

    overlay_image = cat(3, R, G, B);

    evidence_result = struct(...
        'overlay_image', overlay_image, ...
        'referral', referral, ...
        'why_refer', why_refer, ...
        'evidence_list', {evidence_list} ...
    );
end
