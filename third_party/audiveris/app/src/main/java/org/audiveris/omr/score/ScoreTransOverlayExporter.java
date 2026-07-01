//------------------------------------------------------------------------------------------------//
package org.audiveris.omr.score;

import org.audiveris.omr.sheet.Sheet;
import org.audiveris.omr.sheet.SheetStub;
import org.audiveris.omr.sheet.SystemInfo;
import org.audiveris.omr.sheet.ui.SheetGradedPainter;
import org.audiveris.omr.sig.inter.AbstractNoteInter;
import org.audiveris.omr.sig.inter.AbstractPauseInter;
import org.audiveris.omr.sig.inter.AlterInter;
import org.audiveris.omr.sig.inter.ArpeggiatoInter;
import org.audiveris.omr.sig.inter.ArticulationInter;
import org.audiveris.omr.sig.inter.BowInter;
import org.audiveris.omr.sig.inter.DynamicsInter;
import org.audiveris.omr.sig.inter.FermataInter;
import org.audiveris.omr.sig.inter.FingeringInter;
import org.audiveris.omr.sig.inter.Inter;
import org.audiveris.omr.sig.inter.OrnamentInter;
import org.audiveris.omr.sig.inter.PluckingInter;
import org.audiveris.omr.sig.inter.SlurInter;
import org.audiveris.omr.sig.inter.TupletInter;

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
import java.util.List;
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
        json.append("{\"version\":1,\"sheets\":[");
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
                if (!inter.isRemoved() && inter instanceof AbstractNoteInter note) {
                    exportedSourceIds.addAll(ScoreTransProvenance.sourceIds(note));
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
            appendElement(json, inter, bounds);
        }
        json.append("]}");
    }

    private static void appendElement (StringBuilder json,
                                       Inter inter,
                                       Rectangle bounds)
    {
        final String sourceId = ScoreTransProvenance.sourceId(inter);
        json.append("{\"source_id\":\"")
                .append(sourceId)
                .append("\",\"inter_id\":")
                .append(inter.getId())
                .append(",\"shape\":\"")
                .append(escape(String.valueOf(inter.getShape())))
                .append("\",\"grade\":")
                .append(String.format(java.util.Locale.ROOT, "%.6f", inter.getBestGrade()))
                .append(",\"bounds\":{\"x\":")
                .append(bounds.x)
                .append(",\"y\":")
                .append(bounds.y)
                .append(",\"width\":")
                .append(bounds.width)
                .append(",\"height\":")
                .append(bounds.height)
                .append("},\"hit_path\":\"")
                .append(escape(svgPath(hitArea(inter, bounds), bounds)))
                .append("\",\"musicxml_locator\":{\"attribute\":\"id\",\"contains\":\"")
                .append(xmlRole(inter))
                .append("-")
                .append(sourceId.replace(':', '-'))
                .append("\"}}");
    }

    private static boolean isClickableSemantic (Inter inter)
    {
        return inter instanceof AbstractNoteInter
                || inter instanceof AlterInter
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
                || inter instanceof ArpeggiatoInter;
    }

    private static String xmlRole (Inter inter)
    {
        if (inter instanceof AbstractNoteInter) return "n";
        if (inter instanceof AlterInter) return "a";
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

        return area;
    }

    private static String svgPath (Area area,
                                   Rectangle fallback)
    {
        if (area == null || area.isEmpty()) {
            return "M" + fallback.x + " " + fallback.y + "h" + fallback.width + "v"
                    + fallback.height + "h-" + fallback.width + "Z";
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
}
