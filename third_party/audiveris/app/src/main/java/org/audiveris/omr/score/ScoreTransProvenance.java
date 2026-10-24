//------------------------------------------------------------------------------------------------//
package org.audiveris.omr.score;

import org.audiveris.omr.sig.SIGraph;
import org.audiveris.omr.sig.inter.AbstractChordInter;
import org.audiveris.omr.sig.inter.AbstractNoteInter;
import org.audiveris.omr.sig.inter.AbstractPauseInter;
import org.audiveris.omr.sig.inter.AlterInter;
import org.audiveris.omr.sig.inter.ArpeggiatoInter;
import org.audiveris.omr.sig.inter.ArticulationInter;
import org.audiveris.omr.sig.inter.AugmentationDotInter;
import org.audiveris.omr.sig.inter.BowInter;
import org.audiveris.omr.sig.inter.DynamicsInter;
import org.audiveris.omr.sig.inter.FermataInter;
import org.audiveris.omr.sig.inter.FingeringInter;
import org.audiveris.omr.sig.inter.HeadInter;
import org.audiveris.omr.sig.inter.Inter;
import org.audiveris.omr.sig.inter.OrnamentInter;
import org.audiveris.omr.sig.inter.PluckingInter;
import org.audiveris.omr.sig.inter.SlurInter;
import org.audiveris.omr.sig.inter.TupletInter;
import org.audiveris.omr.sig.relation.ChordArpeggiatoRelation;
import org.audiveris.omr.sig.relation.ChordArticulationRelation;
import org.audiveris.omr.sig.relation.ChordBowRelation;
import org.audiveris.omr.sig.relation.ChordDynamicsRelation;
import org.audiveris.omr.sig.relation.ChordOrnamentRelation;
import org.audiveris.omr.sig.relation.ChordPauseRelation;
import org.audiveris.omr.sig.relation.FermataChordRelation;
import org.audiveris.omr.sig.relation.Relation;
import org.audiveris.omr.sig.relation.SlurHeadRelation;
import org.audiveris.omr.util.HorizontalSide;

import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

/**
 * Utilities shared by Score Trans' MusicXML provenance and overlay sidecar exporters.
 */
public final class ScoreTransProvenance
{
    private ScoreTransProvenance ()
    {
    }

    /**
     * Build an application-level source key.
     *
     * @param inter source interpretation
     * @return source key, for example {@code s1:i42}
     */
    public static String sourceId (Inter inter)
    {
        final int sheet = inter.getSig().getSystem().getSheet().getStub().getNumber();
        return "s" + sheet + ":i" + inter.getId();
    }

    /**
     * Build the schema-valid MusicXML note ID carrying every exact Audiveris source used for the
     * note. A role can occur more than once; a numeric suffix keeps every field unique.
     *
     * @param note source note or rest
     * @return MusicXML XML-ID
     */
    public static String noteXmlId (AbstractNoteInter note)
    {
        final LinkedHashMap<String, Inter> sources = collectSources(note);
        final StringBuilder id = new StringBuilder("st");
        for (Map.Entry<String, Inter> entry : sources.entrySet()) {
            final Inter source = entry.getValue();
            final int sheet = source.getSig().getSystem().getSheet().getStub().getNumber();
            id.append("__")
                    .append(entry.getKey())
                    .append("-s")
                    .append(sheet)
                    .append("-i")
                    .append(source.getId());
        }
        return id.toString();
    }

    /**
     * Report every source ID that is provably represented by this MusicXML note.
     *
     * @param note source note or rest
     * @return exact application source IDs
     */
    public static Set<String> sourceIds (AbstractNoteInter note)
    {
        final Set<String> ids = new LinkedHashSet<>();
        for (Inter source : collectSources(note).values()) {
            ids.add(sourceId(source));
        }
        return ids;
    }

    private static LinkedHashMap<String, Inter> collectSources (AbstractNoteInter note)
    {
        final LinkedHashMap<String, Inter> sources = new LinkedHashMap<>();
        put(sources, "n", note);

        if (note instanceof HeadInter head) {
            final AlterInter accidental = head.getAccidental();
            if (accidental != null) {
                put(sources, "a", accidental);
            }
            final FingeringInter fingering = head.getFingering();
            if (fingering != null) {
                put(sources, "fi", fingering);
            }
            final PluckingInter plucking = head.getPlucking();
            if (plucking != null) {
                put(sources, "pl", plucking);
            }
        }

        final AugmentationDotInter firstDot = note.getFirstAugmentationDot();
        if (firstDot != null) {
            put(sources, "ad", firstDot);
            final AugmentationDotInter secondDot = firstDot.getSecondAugmentationDot();
            if (secondDot != null) {
                put(sources, "ad", secondDot);
            }
        }

        final SIGraph sig = note.getSig();
        final AbstractChordInter chord = note.getChord();
        // A loose note/rest may not belong to any chord yet. It still has its
        // own source id (and possibly slur relations), so keep exporting it
        // instead of failing the whole sidecar with a NullPointerException.
        final boolean firstInChord = chord != null && chord.getNotes().indexOf(note) == 0;

        if (firstInChord) {
            for (Relation relation : sig.edgesOf(chord)) {
                final Inter other = sig.getOppositeInter(chord, relation);
                if (relation instanceof ChordArticulationRelation
                        && other instanceof ArticulationInter) {
                    put(sources, "ar", other);
                } else if (relation instanceof ChordOrnamentRelation
                        && other instanceof OrnamentInter) {
                    put(sources, "or", other);
                } else if (relation instanceof ChordDynamicsRelation
                        && other instanceof DynamicsInter) {
                    put(sources, "dy", other);
                } else if (relation instanceof ChordBowRelation && other instanceof BowInter) {
                    put(sources, "bo", other);
                } else if (relation instanceof ChordPauseRelation
                        && other instanceof AbstractPauseInter) {
                    put(sources, "pa", other);
                } else if (relation instanceof ChordArpeggiatoRelation
                        && other instanceof ArpeggiatoInter) {
                    put(sources, "ap", other);
                } else if (relation instanceof FermataChordRelation
                        && other instanceof FermataInter) {
                    put(sources, "fe", other);
                }
            }

            final TupletInter tuplet = chord.getTuplet();
            if (tuplet != null) {
                put(sources, "tu", tuplet);
            }
        }

        for (Relation relation : sig.getRelations(note, SlurHeadRelation.class)) {
            final SlurInter slur = (SlurInter) sig.getOppositeInter(note, relation);
            final String prefix = slur.isTie() ? "t" : "s";
            final String role = prefix
                    + ((slur.getHead(HorizontalSide.LEFT) == note) ? "s" : "e");
            put(sources, role, slur);
        }

        return sources;
    }

    private static void put (LinkedHashMap<String, Inter> sources,
                             String role,
                             Inter inter)
    {
        String key = role;
        int suffix = 2;
        while (sources.containsKey(key)) {
            key = role + suffix++;
        }
        sources.put(key, inter);
    }
}
