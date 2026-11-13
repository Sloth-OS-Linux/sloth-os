#pragma once
// The list of KDE's settings pages, with their names in the user's language (from the pages' own metadata).
#include <QObject>
#include <QVariantList>
#include <QtQml/qqmlregistration.h>

class KcmCatalog : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    explicit KcmCatalog(QObject *parent = nullptr);
    // [{id, name, description, icon, category, keywords, widget}]: every desktop settings page.
    // widget = true: an older page that only opens in its own window (kcmshell6).
    Q_INVOKABLE QVariantList modules() const;
};
