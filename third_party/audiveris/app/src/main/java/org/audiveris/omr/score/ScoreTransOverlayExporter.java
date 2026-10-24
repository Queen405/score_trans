//------------------------------------------------------------------------------------------------//
package org.audiveris.omr.score;

import org.audiveris.omr.sheet.Sheet;
import org.audiveris.omr.sheet.SheetStub;
import org.audiveris.omr.sheet.SystemInfo;
import org.audiveris.omr.sheet.ui.SheetGradedPainter;
import org.audiveris.omr.classifier.Evaluation;
import org.audiveris.omr.classifier.ShapeClassifier;
import org.audiveris.omr.glyph.Glyph;
import org.audiveris.omr.glyph.GlyphFactory;
import org.audiveris.omr.glyph.GlyphGroup;
import org.audiveris.omr.glyph.Shape;
import org.audiveris.omr.glyph.ShapeSet;
import org.audiveris.omr.sig.inter.AbstractNoteInter;
import org.audiveris.omr.sig.inter.AbstractPauseInter;
import org.audiveris.omr.sig.inter.AbstractTimeInter;
import org.audiveris.omr.sig.inter.RestInter;
import org.audiveris.omr.sig.inter.AlterInter;
import org.audiveris.omr.sig.inter.ArpeggiatoInter;
import org.audiveris.omr.sig.inter.ArticulationInter;
import org.audiveris.omr.sig.inter.AugmentationDotInter;
import org.audiveris.omr.sig.inter.BowInter;
import org.audiveris.omr.sig.inter.ClefInter;
import org.audiveris.omr.sig.inter.DynamicsInter;
import org.audiveris.omr.sig.inter.FermataInter;
import org.audiveris.omr.sig.inter.FingeringInter;
import org.audiveris.omr.sig.inter.Inter;
import org.audiveris.omr.sig.inter.KeyInter;
import org.audiveris.omr.sig.inter.OrnamentInter;
import org.audiveris.omr.sig.inter.PedalInter;
import org.audiveris.omr.sig.inter.PluckingInter;
import org.audiveris.omr.sig.inter.SlurInter;
import org.audiveris.omr.sig.inter.TupletInter;
import org.audiveris.omr.sig.inter.TimePairInter;
import org.audiveris.omr.sig.inter.TimeNumberInter;
import org.audiveris.omr.sig.inter.WedgeInter;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.awt.Graphics2D;
import java.awt.Point;
import java.awt.Rectangle;
import java.awt.RenderingHints;
import java.awt.geom.Area;
import java.awt.geom.PathIterator;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import javax.imageio.ImageIO;

/**
 * Exports the exact Data-view paint layer and its semantic hit geometry for Score Trans.
 */
public final class ScoreTransOverlayExporter
{
    private static final Logger logger = LoggerFactory.getLogger(
            ScoreTransOverlayExporter.class);

    private ScoreTransOverlayExporter ()
    {
    }

    /**
     * Export one transparent PNG per sheet and a versioned sidecar.
     *
     * @param stubs      selected valid sheets
     * @param outputDir Audiveris output directory
     * @throws IOException if an output cannot be written
     */
    public static void export (List<SheetStub> stubs,
                               Path outputDir)
        throws IOException
    {
        Files.createDirectories(outputDir);
        final StringBuilder json = new StringBuilder();
        json.append("{\"version\":2,\"sheets\":[");
        boolean firstSheet = true;

        for (SheetStub stub : stubs) {
            final Sheet sheet = stub.getSheet();
            if (sheet == null || sheet.getWidth() <= 0 || sheet.getHeight() <= 0) {
                continue;
            }

            final String overlayName = "overlay_sheet" + stub.getNumber() + ".png";
            writeOverlay(sheet, outputDir.resolve(overlayName));

            if (!firstSheet) {
                json.append(',');
            }
            firstSheet = false;
            appendSheet(json, sheet, stub.getNumber(), overlayName);
        }
        json.append("]}");
        Files.writeString(
                outputDir.resolve("score-link-map.json"),
                json.toString(),
                StandardCharsets.UTF_8);
        logger.info("Score Trans overlay sidecar exported to {}", outputDir);
    }

    private static void writeOverlay (Sheet sheet,
                                      Path path)
        throws IOException
    {
        final BufferedImage image = new BufferedImage(
                sheet.getWidth(),
                sheet.getHeight(),
                BufferedImage.TYPE_INT_ARGB);
        final Graphics2D g = image.createGraphics();
        try {
            g.setClip(0, 0, image.getWidth(), image.getHeight());
            g.setRenderingHint(
                    RenderingHints.KEY_ANTIALIASING,
                    RenderingHints.VALUE_ANTIALIAS_ON);
            g.setRenderingHint(
                    RenderingHints.KEY_TEXT_ANTIALIASING,
                    RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
            new SheetGradedPainter(sheet, g, false, false, true).process();
        } finally {
            g.dispose();
        }
        ImageIO.write(image, "png", path.toFile());
    }

    private static void appendSheet (StringBuilder json,
                                     Sheet sheet,
                                     int sheetIndex,
                                     String overlayName)
    {
        json.append("{\"sheet_index\":")
                .append(sheetIndex)
                .append(",\"width\":")
                .append(sheet.getWidth())
                .append(",\"height\":")
                .append(sheet.getHeight())
                .append(",\"overlay_file\":\"")
                .append(overlayName)
                .append("\",\"elements\":[");

        final List<Inter> elements = new ArrayList<>();
        final Set<String> exportedSourceIds = new HashSet<>();
        for (SystemInfo system : sheet.getSystems()) {
            for (Inter inter : system.getSig().vertexSet()) {
                if (inter.isRemoved()) {
                    continue;
                }
                if (inter instanceof AbstractNoteInter note) {
                    exportedSourceIds.addAll(ScoreTransProvenance.sourceIds(note));
                } else if (inter instanceof ClefInter
                        || inter instanceof KeyInter
                        || inter instanceof AbstractTimeInter
                        || inter instanceof TimePairInter) {
                    exportedSourceIds.add(ScoreTransProvenance.sourceId(inter));
                } else if (inter instanceof WedgeInter || inter instanceof PedalInter) {
                    exportedSourceIds.add(ScoreTransProvenance.sourceId(inter));
                }
            }
        }

        for (SystemInfo system : sheet.getSystems()) {
            for (Inter inter : system.getSig().vertexSet()) {
                if (!inter.isRemoved()
                        && isClickableSemantic(inter)
                        && exportedSourceIds.contains(ScoreTransProvenance.sourceId(inter))) {
                    elements.add(inter);
                }
            }
        }
        elements.sort(Comparator.comparingInt(Inter::getId));

        boolean first = true;
        for (Inter inter : elements) {
            final Rectangle bounds = inter.getBounds();
            if (bounds == null || bounds.isEmpty()) {
                continue;
            }
            if (!first) {
                json.append(',');
            }
            first = false;
            appendElement(json, inter, bounds, sheet);
        }
        appendSuspiciousGlyphs(json, sheet);
        json.append("}");
    }

    private static void appendSuspiciousGlyphs (StringBuilder json,
                                                 Sheet sheet)
    {
        json.append("],\"glyphs\":[");
        final Set<Integer> referenced = new HashSet<>();
        for (SystemInfo system : sheet.getSystems()) {
            for (Inter inter : system.getSig().vertexSet()) {
                if (inter.getGlyph() != null) referenced.add(inter.getGlyph().getId());
            }
        }
        boolean first = true;
        final List<Glyph> suspicious = new ArrayList<>();
        final int minimumHeadDimension = Math.max(4, (int) Math.ceil(sheet.getInterline() * 0.4));
        for (Glyph glyph : sheet.getGlyphIndex().getEntities()) {
            final Rectangle bounds = glyph.getBounds();
            if (bounds == null || bounds.isEmpty()
                    || !glyph.getGroups().contains(GlyphGroup.SYMBOL)
                    || glyph.getWidth() < minimumHeadDimension
                    || glyph.getWidth() > sheet.getInterline() * 4
                    || glyph.getHeight() < minimumHeadDimension
                    || glyph.getHeight() > sheet.getInterline() * 4) {
                continue;
            }
            if (referenced.contains(glyph.getId())) {
                continue;
            }
            final boolean repetitive = isRepeatedAcrossRows(
                    glyph, sheet.getGlyphIndex().getEntities(), sheet.getInterline());
            if (repetitive) continue;

            final List<ScoreTransCandidateRegistry.Candidate> candidates = noteheadCandidates(
                    sheet, bounds, glyph);
            if (candidates.isEmpty()) continue;
            suspicious.add(glyph);
        }
        for (Glyph glyph : suspicious) {
            final Rectangle bounds = glyph.getBounds();
            final List<ScoreTransCandidateRegistry.Candidate> candidates = noteheadCandidates(
                    sheet, bounds, glyph);
            if (!first) json.append(',');
            first = false;
            json.append("{\"glyph_id\":\"s").append(sheet.getStub().getNumber())
                    .append(":g").append(glyph.getId()).append("\",\"bounds\":{\"x\":")
                    .append(bounds.x).append(",\"y\":").append(bounds.y)
                    .append(",\"width\":").append(bounds.width)
                    .append(",\"height\":").append(bounds.height)
                    .append("},\"hit_path\":\"").append(escape(svgPath(glyphArea(glyph))))
                    .append("\",\"suspicious\":true,\"tag\":\"unrecognized-head\"")
                    .append(",\"shape\":\"UNKNOWN\",\"grade\":0,\"shape_candidates\":")
                    .append(candidateJson(candidates))
                    .append('}');
        }
        json.append(']');
    }

    private static boolean isRepeatedAcrossRows (Glyph target,
                                                 List<Glyph> glyphs,
                                                 int interline)
    {
        final Rectangle box = target.getBounds();
        if (box == null) return false;
        final List<Integer> rowPositions = new ArrayList<>();
        final int xTolerance = Math.max(2, interline / 3);
        for (Glyph other : glyphs) {
            if (other.getId() == target.getId()) continue;
            final Rectangle otherBox = other.getBounds();
            if (otherBox == null || otherBox.isEmpty()) continue;
            if (Math.abs(otherBox.getCenterX() - box.getCenterX()) <= xTolerance
                    && Math.abs(otherBox.width - box.width) <= Math.max(2, interline / 3)
                    && Math.abs(otherBox.height - box.height) <= Math.max(2, interline / 3)) {
                rowPositions.add(otherBox.y + (otherBox.height / 2));
            }
        }
        rowPositions.add(box.y + (box.height / 2));
        rowPositions.sort(Integer::compareTo);

        final List<Integer> largeGaps = new ArrayList<>();
        for (int i = 1; i < rowPositions.size(); i++) {
            final int gap = rowPositions.get(i) - rowPositions.get(i - 1);
            if (gap >= interline * 4) largeGaps.add(gap);
        }
        for (int i = 1; i < largeGaps.size(); i++) {
            final int previous = largeGaps.get(i - 1);
            final int current = largeGaps.get(i);
            if (Math.abs(previous - current) <= Math.max(interline * 2, previous / 5)) {
                return true;
            }
        }
        return false;
    }

    private static Area glyphArea (Glyph glyph)
    {
        final Area area = new Area();
        final Rectangle bounds = glyph.getBounds();
        for (int y = bounds.y; y < bounds.y + bounds.height; y++) {
            int start = -1;
            for (int x = bounds.x; x <= bounds.x + bounds.width; x++) {
                boolean ink = x < bounds.x + bounds.width && glyph.getRunTable() != null
                        && glyph.getRunTable().contains(new Point(x - bounds.x, y - bounds.y));
                if (ink && start < 0) start = x;
                else if (!ink && start >= 0) {
                    area.add(new Area(new Rectangle(start, y, x - start, 1)));
                    start = -1;
                }
            }
        }
        return area;
    }

    private static void appendElement (StringBuilder json,
                                       Inter inter,
                                       Rectangle bounds,
                                       Sheet sheet)
    {
        final String sourceId = ScoreTransProvenance.sourceId(inter);
        json.append("{\"source_id\":\"")
                .append(sourceId)
                .append("\",\"inter_id\":")
                .append(inter.getId())
                .append(",\"shape\":\"")
                .append(escape(shapeForInter(inter)))
                .append("\",\"grade\":")
                .append(String.format(java.util.Locale.ROOT, "%.6f", inter.getBestGrade()))
                .append(",\"candidates\":")
                .append(candidateJson(inter, sheet, bounds))
                .append(",\"bounds\":{\"x\":")
                .append(bounds.x)
                .append(",\"y\":")
                .append(bounds.y)
                .append(",\"width\":")
                .append(bounds.width)
                .append(",\"height\":")
                .append(bounds.height)
                .append("},\"hit_path\":\"")
                .append(escape(svgPath(hitArea(inter, bounds))))
                .append("\",\"musicxml_locator\":{\"attribute\":\"id\",\"contains\":\"")
                .append(xmlRole(inter))
                .append("-")
                .append(sourceId.replace(':', '-'))
                .append("\"}}");
    }

    private static String candidateJson (Inter inter)
    {
        final Sheet sheet = inter.getSig().getSystem().getSheet();
        final Rectangle bounds = inter.getBounds();
        return bounds == null ? "[]" : candidateJson(inter, sheet, bounds);
    }

    private static String candidateJson (Inter inter, Sheet sheet, Rectangle bounds)
    {
        return exportCandidateJson(candidatesFor(inter, sheet, candidateTag(inter)));
    }

    private static String candidateJson (List<ScoreTransCandidateRegistry.Candidate> candidates)
    {
        final StringBuilder json = new StringBuilder("[");
        for (int i = 0; i < candidates.size(); i++) {
            if (i > 0) json.append(',');
            final ScoreTransCandidateRegistry.Candidate candidate = candidates.get(i);
            json.append("{\"shape\":\"").append(candidate.shape())
                    .append("\",\"score\":")
                    .append(String.format(java.util.Locale.ROOT, "%.6f", candidate.score()))
                    .append(",\"score_kind\":\"")
                    .append(ScoreTransCandidateRegistry.SCORE_KIND).append("\"}");
        }
        return json.append(']').toString();
    }

    private static String exportCandidateJson (List<ExportCandidate> candidates)
    {
        final StringBuilder json = new StringBuilder("[");
        for (int i = 0; i < candidates.size(); i++) {
            if (i > 0) json.append(',');
            final ExportCandidate candidate = candidates.get(i);
            json.append("{\"shape\":\"").append(candidate.shape())
                    .append("\",\"score\":")
                    .append(String.format(java.util.Locale.ROOT, "%.6f", candidate.score()))
                    .append(",\"score_kind\":\"").append(candidate.scoreKind()).append("\"}");
        }
        return json.append(']').toString();
    }

    private static List<ExportCandidate> candidatesFor (Inter inter,
                                                         Sheet sheet,
                                                         String family)
    {
        if (family == null) return List.of();
        if ("time-whole".equals(family) && inter instanceof TimePairInter pair) {
            return timePairCandidates(pair, sheet);
        }
        final Map<String, ExportCandidate> byShape = new LinkedHashMap<>();
        if ("head".equals(family)) {
            for (ScoreTransCandidateRegistry.Candidate candidate
                    : noteheadCandidates(sheet, inter.getBounds(), inter.getGlyph())) {
                byShape.put(candidate.shape(), new ExportCandidate(
                        candidate.shape(), candidate.score(),
                        ScoreTransCandidateRegistry.SCORE_KIND));
            }
        }

        final Glyph glyph;
        if (inter.getGlyph() != null) {
            glyph = inter.getGlyph();
        } else if ("clef".equals(family) || "key".equals(family)) {
            // Compound clefs/keys may need their component glyphs reunited.
            // Do not synthesize glyphs for large slur/tuplet bounds: that scans
            // the whole sheet and classifies unrelated notes inside the bounds.
            glyph = glyphForInterBounds(sheet, inter.getBounds());
        } else {
            glyph = null;
        }
        if (glyph != null) {
            final Evaluation[] evaluations;
            try {
                evaluations = ShapeClassifier.getInstance().getNaturalEvaluations(
                        glyph, Math.max(1, sheet.getInterline()));
            } catch (RuntimeException ex) {
                logger.debug("Could not evaluate candidates for inter {}", inter.getId(), ex);
                return sortedTopCandidates(inter, byShape);
            }
            for (Evaluation evaluation : evaluations) {
                final String shape = evaluation.shape.toString();
                if (!isSupportedCandidate(family, shape)) continue;
                byShape.merge(shape, new ExportCandidate(
                                shape, evaluation.grade, "audiveris_shape_classifier"),
                        (existing, candidate) -> candidate.score() > existing.score()
                                ? candidate : existing);
            }
        }
        return sortedTopCandidates(inter, byShape);
    }

    /** Compose real classifier scores for numerator and denominator glyphs into time signatures. */
    private static List<ExportCandidate> timePairCandidates (TimePairInter pair, Sheet sheet)
    {
        final Map<Integer, Double> numeratorScores = timeNumberScores(pair.getNum(), sheet);
        final Map<Integer, Double> denominatorScores = timeNumberScores(pair.getDen(), sheet);
        final int[][] signatures = {
                {4, 4}, {2, 2}, {2, 4}, {3, 4}, {5, 4}, {6, 4},
                {3, 8}, {6, 8}, {9, 8}, {12, 8},
        };
        final Map<String, ExportCandidate> candidates = new LinkedHashMap<>();
        for (int[] signature : signatures) {
            final Double numerator = numeratorScores.get(signature[0]);
            final Double denominator = denominatorScores.get(signature[1]);
            if (numerator == null || denominator == null) continue;
            final String shape = timeShape(signature[0], signature[1]);
            final double score = Math.sqrt(Math.max(0.0, numerator) * Math.max(0.0, denominator));
            candidates.put(shape, new ExportCandidate(
                    shape, score, "audiveris_shape_classifier_composite"));
        }
        final String currentShape = shapeForInter(pair);
        candidates.putIfAbsent(currentShape, new ExportCandidate(
                currentShape, pair.getBestGrade(), "audiveris_inter_grade"));
        return topCandidates(candidates, currentShape);
    }

    private static Map<Integer, Double> timeNumberScores (TimeNumberInter number, Sheet sheet)
    {
        if (number == null) return Map.of();
        final Glyph glyph = number.getGlyph() != null
                ? number.getGlyph() : glyphForInterBounds(sheet, number.getBounds());
        if (glyph == null) return Map.of();
        final Map<Integer, Double> scores = new LinkedHashMap<>();
        try {
            for (Evaluation evaluation : ShapeClassifier.getInstance().getNaturalEvaluations(
                    glyph, Math.max(1, sheet.getInterline()))) {
                final Integer value = timeNumberValue(evaluation.shape);
                if (value != null) scores.merge(value, evaluation.grade, Math::max);
            }
        } catch (RuntimeException ex) {
            logger.debug("Could not evaluate time-signature number {}", number.getId(), ex);
        }
        return scores;
    }

    private static Integer timeNumberValue (Shape shape)
    {
        return switch (shape) {
            case TIME_ZERO -> 0;
            case TIME_ONE -> 1;
            case TIME_TWO -> 2;
            case TIME_THREE -> 3;
            case TIME_FOUR -> 4;
            case TIME_FIVE -> 5;
            case TIME_SIX -> 6;
            case TIME_SEVEN -> 7;
            case TIME_EIGHT -> 8;
            case TIME_NINE -> 9;
            case TIME_TWELVE -> 12;
            case TIME_SIXTEEN -> 16;
            default -> null;
        };
    }

    private static String timeShape (int numerator, int denominator)
    {
        return switch (numerator + "/" + denominator) {
            case "4/4" -> "TIME_FOUR_FOUR";
            case "2/2" -> "TIME_TWO_TWO";
            case "2/4" -> "TIME_TWO_FOUR";
            case "3/4" -> "TIME_THREE_FOUR";
            case "5/4" -> "TIME_FIVE_FOUR";
            case "6/4" -> "TIME_SIX_FOUR";
            case "3/8" -> "TIME_THREE_EIGHT";
            case "6/8" -> "TIME_SIX_EIGHT";
            case "9/8" -> "TIME_NINE_EIGHT";
            case "12/8" -> "TIME_TWELVE_EIGHT";
            default -> "TIME_CUSTOM";
        };
    }

    private static List<ExportCandidate> sortedTopCandidates (Inter inter,
                                                               Map<String, ExportCandidate> byShape)
    {
        final String currentShape = shapeForInter(inter);
        byShape.putIfAbsent(currentShape, new ExportCandidate(
                currentShape, inter.getBestGrade(), "audiveris_inter_grade"));
        return topCandidates(byShape, currentShape);
    }

    /**
     * Report the strongest candidates, always keeping the recognized shape selectable.
     * <p>
     * A user who switches away from the original classification must be able to switch
     * back, so the current shape replaces the weakest entry when five stronger
     * candidates would otherwise hide it.
     */
    private static List<ExportCandidate> topCandidates (Map<String, ExportCandidate> byShape,
                                                        String currentShape)
    {
        final List<ExportCandidate> sorted = new ArrayList<>(byShape.values());
        sorted.replaceAll(ScoreTransOverlayExporter::normalizeCandidateScore);
        sorted.sort(Comparator.comparingDouble(ExportCandidate::score).reversed());
        final List<ExportCandidate> top = new ArrayList<>(
                sorted.subList(0, Math.min(5, sorted.size())));
        final boolean hasCurrent = top.stream()
                .anyMatch(candidate -> candidate.shape().equals(currentShape));
        if (!hasCurrent) {
            sorted.stream()
                    .filter(candidate -> candidate.shape().equals(currentShape))
                    .findFirst()
                    .ifPresent(current -> {
                        if (top.size() == 5) top.remove(top.size() - 1);
                        top.add(current);
                    });
        }
        return top;
    }

    private static String shapeForInter (Inter inter)
    {
        if (inter instanceof TimePairInter pair && pair.getTimeRational() != null) {
            return switch (pair.getTimeRational().toString()) {
                case "4/4" -> "TIME_FOUR_FOUR";
                case "2/2" -> "TIME_TWO_TWO";
                case "2/4" -> "TIME_TWO_FOUR";
                case "3/4" -> "TIME_THREE_FOUR";
                case "5/4" -> "TIME_FIVE_FOUR";
                case "6/4" -> "TIME_SIX_FOUR";
                case "3/8" -> "TIME_THREE_EIGHT";
                case "6/8" -> "TIME_SIX_EIGHT";
                case "9/8" -> "TIME_NINE_EIGHT";
                case "12/8" -> "TIME_TWELVE_EIGHT";
                default -> "TIME_CUSTOM";
            };
        }
        return String.valueOf(inter.getShape());
    }

    /** Convert Audiveris' categorical inter grades and neural scores to one ranking range. */
    private static ExportCandidate normalizeCandidateScore (ExportCandidate candidate)
    {
        double score = candidate.score();
        if ("audiveris_inter_grade".equals(candidate.scoreKind())) {
            if (score >= Evaluation.MANUAL) {
                score = 1.0;
            } else if (score >= Evaluation.ALGORITHM) {
                score = 0.99;
            }
        }
        score = Double.isFinite(score) ? Math.max(0.0, Math.min(1.0, score)) : 0.0;
        return new ExportCandidate(candidate.shape(), score, candidate.scoreKind());
    }

    private static List<ScoreTransCandidateRegistry.Candidate> noteheadCandidates (Sheet sheet,
                                                                                    Rectangle bounds,
                                                                                    Glyph glyph)
    {
        final List<ScoreTransCandidateRegistry.Candidate> stored =
                ScoreTransCandidateRegistry.candidatesFor(glyph);
        final List<ScoreTransCandidateRegistry.Candidate> filtered = stored.stream()
                .filter(candidate -> isSupportedCandidate("head", candidate.shape()))
                .toList();
        if (!filtered.isEmpty()) return filtered;
        return ScoreTransCandidateRegistry.candidatesNear(
                        sheet.getScoreTransNoteCandidateLocations(),
                        bounds,
                        sheet.getInterline() * 2).stream()
                .filter(candidate -> isSupportedCandidate("head", candidate.shape()))
                .toList();
    }

    /** Build a temporary classifier glyph for compound inters that do not persist one. */
    private static Glyph glyphForInterBounds (Sheet sheet, Rectangle bounds)
    {
        if (bounds == null || bounds.isEmpty()) return null;
        final List<Glyph> parts = new ArrayList<>();
        for (Glyph glyph : sheet.getGlyphIndex().getEntities()) {
            if (!glyph.getGroups().contains(GlyphGroup.SYMBOL)
                    || glyph.getRunTable() == null) continue;
            final Rectangle glyphBounds = glyph.getBounds();
            if (glyphBounds == null || !bounds.contains(glyphBounds.getCenterX(),
                    glyphBounds.getCenterY())) continue;
            final Rectangle intersection = bounds.intersection(glyphBounds);
            final double glyphArea = (double) glyphBounds.width * glyphBounds.height;
            final double overlap = (double) intersection.width * intersection.height;
            if (glyphArea > 0 && overlap / glyphArea >= 0.7) parts.add(glyph);
        }
        if (parts.isEmpty()) return null;
        return parts.size() == 1 ? parts.get(0) : GlyphFactory.buildGlyph(parts);
    }

    private static boolean isSupportedCandidate (String family, String shape)
    {
        return switch (family) {
            case "head" -> Set.of(
                    "NOTEHEAD_BLACK", "NOTEHEAD_BLACK_SMALL", "NOTEHEAD_CROSS",
                    "NOTEHEAD_DIAMOND_FILLED", "NOTEHEAD_TRIANGLE_DOWN_FILLED",
                    "NOTEHEAD_CIRCLE_X", "NOTEHEAD_VOID", "NOTEHEAD_VOID_SMALL",
                    "NOTEHEAD_CROSS_VOID", "NOTEHEAD_DIAMOND_VOID",
                    "NOTEHEAD_TRIANGLE_DOWN_VOID", "NOTEHEAD_CIRCLE_X_VOID",
                    "WHOLE_NOTE", "WHOLE_NOTE_SMALL", "WHOLE_NOTE_CROSS",
                    "WHOLE_NOTE_DIAMOND", "WHOLE_NOTE_TRIANGLE_DOWN",
                    "WHOLE_NOTE_CIRCLE_X").contains(shape);
            case "rest" -> Set.of("QUARTER_REST", "HALF_REST", "WHOLE_REST",
                    "EIGHTH_REST", "ONE_16TH_REST", "ONE_32ND_REST", "ONE_64TH_REST",
                    "ONE_128TH_REST", "BREVE_REST", "LONG_REST", "HW_REST")
                    .contains(shape);
            case "alter" -> ShapeSet.Accidentals.getShapes().contains(Shape.valueOf(shape));
            case "clef" -> ShapeSet.Clefs.contains(Shape.valueOf(shape));
            case "key" -> shape.startsWith("KEY_") || shape.equals("KEY_CANCEL");
            case "time-whole", "time-custom" -> ShapeSet.WholeTimes.contains(Shape.valueOf(shape));
            case "dynamic" -> shape.startsWith("DYNAMICS_") || shape.equals("SFZ")
                    || shape.equals("SF");
            case "wedge" -> shape.equals("CRESCENDO") || shape.equals("DIMINUENDO");
            case "pedal" -> shape.equals("PEDAL_MARK") || shape.equals("PEDAL_UP_MARK");
            case "articulation" -> Set.of("STACCATO", "STACCATISSIMO", "ACCENT",
                    "STRONG_ACCENT", "TENUTO", "MARCATO").contains(shape);
            case "ornament" -> Set.of("MORDENT", "MORDENT_INVERTED", "TURN",
                    "TURN_INVERTED", "TURN_UP", "TURN_SLASH", "TR").contains(shape);
            case "fermata" -> shape.equals("FERMATA") || shape.equals("FERMATA_BELOW");
            case "pause" -> shape.equals("BREATH_MARK") || shape.equals("CAESURA");
            case "slur" -> shape.startsWith("SLUR_") || shape.equals("SLUR");
            case "tuplet" -> shape.equals("TUPLET_THREE") || shape.equals("TUPLET_SIX");
            case "fingering" -> shape.matches("DIGIT_[0-5]");
            case "plucking" -> Set.of("PLUCK_P", "PLUCK_I", "PLUCK_M", "PLUCK_A")
                    .contains(shape);
            case "bow" -> shape.equals("BOW_UP") || shape.equals("BOW_DOWN");
            case "arpeggiato" -> shape.equals("ARPEGGIATO");
            case "augmentation-dot" -> shape.equals("AUGMENTATION_DOT");
            default -> false;
        };
    }

    private static String candidateTag (Inter inter)
    {
        if (inter instanceof TimePairInter) return "time-whole";
        if (inter instanceof SlurInter) return "slur";
        if (inter instanceof TupletInter) return "tuplet";
        if (inter instanceof FingeringInter) return "fingering";
        if (inter instanceof PluckingInter) return "plucking";
        if (inter instanceof BowInter) return "bow";
        if (inter instanceof ArpeggiatoInter) return "arpeggiato";
        if (inter instanceof AugmentationDotInter) return "augmentation-dot";
        // FermataInter is an AbstractPauseInter too, so classify it first or its
        // candidate family is incorrectly restricted to breath marks and caesurae.
        if (inter instanceof FermataInter) return "fermata";
        if (inter instanceof AbstractPauseInter) return "pause";
        if (inter instanceof WedgeInter) return "wedge";
        if (inter instanceof PedalInter) return "pedal";
        if (inter instanceof RestInter) return "rest";
        if (inter instanceof AbstractNoteInter) return "head";
        if (inter instanceof AlterInter) return "alter";
        if (inter instanceof ClefInter) return "clef";
        if (inter instanceof KeyInter) return "key";
        if (inter instanceof AbstractTimeInter) return "time-whole";
        if (inter instanceof DynamicsInter) return "dynamic";
        if (inter instanceof ArticulationInter) return "articulation";
        if (inter instanceof OrnamentInter) return "ornament";
        return null;
    }

    private static boolean isClickableSemantic (Inter inter)
    {
        return inter instanceof AbstractNoteInter
                || inter instanceof AlterInter
                || inter instanceof AugmentationDotInter
                || inter instanceof SlurInter
                || inter instanceof ArticulationInter
                || inter instanceof OrnamentInter
                || inter instanceof DynamicsInter
                || inter instanceof AbstractPauseInter
                || inter instanceof FermataInter
                || inter instanceof TupletInter
                || inter instanceof FingeringInter
                || inter instanceof PluckingInter
                || inter instanceof BowInter
                || inter instanceof ArpeggiatoInter
                || inter instanceof ClefInter
                || inter instanceof KeyInter
                || inter instanceof AbstractTimeInter
                || inter instanceof WedgeInter
                || inter instanceof PedalInter;
    }

    private static String xmlRole (Inter inter)
    {
        if (inter instanceof TimePairInter) return "t";
        if (inter instanceof AbstractNoteInter) return "n";
        if (inter instanceof AlterInter) return "a";
        if (inter instanceof AugmentationDotInter) return "ad";
        if (inter instanceof SlurInter) return "s";
        if (inter instanceof ArticulationInter) return "ar";
        if (inter instanceof OrnamentInter) return "or";
        if (inter instanceof DynamicsInter) return "dy";
        if (inter instanceof TupletInter) return "tu";
        if (inter instanceof FingeringInter) return "fi";
        if (inter instanceof PluckingInter) return "pl";
        if (inter instanceof BowInter) return "bo";
        if (inter instanceof ArpeggiatoInter) return "ap";
        if (inter instanceof FermataInter) return "fe";
        if (inter instanceof ClefInter) return "c";
        if (inter instanceof KeyInter) return "k";
        if (inter instanceof AbstractTimeInter) return "t";
        if (inter instanceof WedgeInter) return "wg";
        if (inter instanceof PedalInter) return "pd";
        return "pa";
    }

    /**
     * Build the same pixel-precise hit area used by Audiveris selection.
     * <p>
     * Some restored inters have no persisted {@link Inter#getArea()} but do retain their glyph.
     * Calling {@link Inter#contains(Point)} also preserves specialized hit rules such as shared
     * note heads.
     */
    private static Area hitArea (Inter inter,
                                 Rectangle bounds)
    {
        if (inter.getArea() != null && !inter.getArea().isEmpty()) {
            return inter.getArea();
        }

        final Area area = new Area();
        final int xMax = bounds.x + bounds.width;
        final int yMax = bounds.y + bounds.height;

        for (int y = bounds.y; y < yMax; y++) {
            int runStart = -1;

            for (int x = bounds.x; x <= xMax; x++) {
                final boolean contained = x < xMax && inter.contains(new Point(x, y));

                if (contained && runStart < 0) {
                    runStart = x;
                } else if (!contained && runStart >= 0) {
                    area.add(new Area(new Rectangle(runStart, y, x - runStart, 1)));
                    runStart = -1;
                }
            }
        }

        if (area.isEmpty() && inter.getGlyph() != null) {
            return glyphArea(inter.getGlyph());
        }

        return area;
    }

    private static String svgPath (Area area)
    {
        if (area == null || area.isEmpty()) {
            // An empty semantic area must not become a bounding-box hit target.
            // Empty paths are non-rendering and non-clickable in the renderer.
            return "";
        }

        final StringBuilder path = new StringBuilder();
        final PathIterator iterator = area.getPathIterator(null, 0.5);
        final double[] values = new double[6];
        while (!iterator.isDone()) {
            final int segment = iterator.currentSegment(values);
            switch (segment) {
                case PathIterator.SEG_MOVETO ->
                    path.append('M').append(number(values[0])).append(' ')
                            .append(number(values[1]));
                case PathIterator.SEG_LINETO ->
                    path.append('L').append(number(values[0])).append(' ')
                            .append(number(values[1]));
                case PathIterator.SEG_QUADTO ->
                    path.append('Q').append(number(values[0])).append(' ')
                            .append(number(values[1])).append(' ')
                            .append(number(values[2])).append(' ')
                            .append(number(values[3]));
                case PathIterator.SEG_CUBICTO ->
                    path.append('C').append(number(values[0])).append(' ')
                            .append(number(values[1])).append(' ')
                            .append(number(values[2])).append(' ')
                            .append(number(values[3])).append(' ')
                            .append(number(values[4])).append(' ')
                            .append(number(values[5]));
                case PathIterator.SEG_CLOSE -> path.append('Z');
                default -> {
                }
            }
            iterator.next();
        }
        return path.toString();
    }

    private static String number (double value)
    {
        return String.format(java.util.Locale.ROOT, "%.2f", value);
    }

    private static String escape (String value)
    {
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private record ExportCandidate (String shape, double score, String scoreKind)
    {
    }
}
